import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

PIOUPIOU_ID = 2031
MAX_AGE_MINUTES = 30

# Ce fichier doit être placé dans scripts/balise_andran.py.
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

MODEL = ROOT / "models" / "model.onnx"
MODEL_CONFIG = ROOT / "models" / "model.onnx.json"

LOGFILE = ROOT / "balise_andran.log"
MAX_LOG_SIZE = 100 * 1024

SILENCE_DEBUT_MS = 500

WAV = ROOT / "BaliseAndran.wav"
WAV_TMP = ROOT / "BaliseAndran_tmp.wav"
MP3 = ROOT / "BaliseAndran.mp3"

# Le MP3 final n'est remplacé qu'après conversion réussie.
MP3_TMP = ROOT / "BaliseAndran_tmp.mp3"


# ============================================================
# DIRECTIONS VALIDÉES
# ============================================================

directions = [
    "nord",
    "nord nord èst",
    "nord èst",
    "èst nord èst",
    "èst",
    "èst sud èst",
    "sud èst",
    "sud sud èst",
    "sud",
    "sud sud ouest",
    "sud ouest",
    "ouest sud ouest",
    "ouest",
    "ouest nord ouest",
    "nord ouest",
    "nord nord ouest",
]


# ============================================================
# JOURNAL
# ============================================================

def rotate_log():
    if not LOGFILE.exists():
        return

    if LOGFILE.stat().st_size < MAX_LOG_SIZE:
        return

    lignes = LOGFILE.read_text(encoding="utf-8").splitlines(
        keepends=True
    )

    LOGFILE.write_text(
        "".join(lignes[len(lignes) // 2:]),
        encoding="utf-8",
    )


def log_message(message):
    rotate_log()

    horodatage = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
    ligne = f"[{horodatage}] {message}"

    print(ligne, flush=True)

    with LOGFILE.open("a", encoding="utf-8") as fichier:
        fichier.write(ligne + "\n")


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():
    log_message("===== DÉMARRAGE =====")
    log_message(f"Dossier de travail : {ROOT}")

    for fichier in (MODEL, MODEL_CONFIG):
        if not fichier.is_file():
            raise FileNotFoundError(
                f"Fichier de voix absent : {fichier}"
            )

    # Nettoyer les fichiers intermédiaires uniquement.
    for fichier in (WAV, WAV_TMP, MP3_TMP):
        fichier.unlink(missing_ok=True)

    url = f"http://api.pioupiou.fr/v1/live/{PIOUPIOU_ID}"
    log_message(f"Lecture balise WindBird {PIOUPIOU_ID}")

    reponse = requests.get(url, timeout=20)
    reponse.raise_for_status()

    mesures = reponse.json()["data"]["measurements"]

    date_mesure = datetime.fromisoformat(
        mesures["date"].replace("Z", "+00:00")
    )

    if date_mesure.tzinfo is None:
        raise ValueError("Date de mesure sans fuseau horaire")

    maintenant = datetime.now(timezone.utc)
    age_minutes = (
        maintenant - date_mesure
    ).total_seconds() / 60.0

    log_message(
        "Heure mesure : "
        + date_mesure.astimezone(timezone.utc).strftime(
            "%d/%m/%Y %H:%M:%S UTC"
        )
    )
    log_message(f"Age mesure = {age_minutes:.1f} minutes")

    champs_vent = (
        "wind_heading",
        "wind_speed_avg",
        "wind_speed_max",
    )

    valeurs_presentes = all(
        mesures.get(champ) is not None
        for champ in champs_vent
    )

    if (
        valeurs_presentes
        and 0 <= age_minutes <= MAX_AGE_MINUTES
    ):
        cap = round(mesures["wind_heading"])
        vent = round(mesures["wind_speed_avg"])
        rafale = round(mesures["wind_speed_max"])

        idx = int((cap / 22.5) + 0.5) % 16
        direction = directions[idx]

        phrase = (
            f"Balise de l'Andran, "
            f"{direction}, "
            f"{vent} kilomètre heure, "
            f"{rafale} maximum."
        )

        log_message("Etat mesure : VALIDE")
        log_message(
            f"Direction={cap}° "
            f"Vent={vent} km/h "
            f"Rafale={rafale} km/h"
        )
    else:
        phrase = (
            "Balise de l'Andran, "
            "mesure non disponible."
        )
        log_message("Etat mesure : NON DISPONIBLE")

    log_message(f"Phrase : {phrase}")

    # --------------------------------------------------------
    # Génération WAV Piper
    # --------------------------------------------------------

    log_message("Génération WAV")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "piper",
            "--model",
            str(MODEL),
            "--length-scale",
            "1.6",
            "--output-file",
            str(WAV),
        ],
        input=phrase + "\n",
        text=True,
        encoding="utf-8",
        check=True,
        timeout=180,
    )

    # --------------------------------------------------------
    # Ajout du silence initial
    # --------------------------------------------------------

    log_message(
        f"Ajout silence début {SILENCE_DEBUT_MS} ms"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            str(WAV),
            "-af",
            f"adelay={SILENCE_DEBUT_MS}:all=1",
            str(WAV_TMP),
        ],
        check=True,
        timeout=60,
    )

    # --------------------------------------------------------
    # Conversion MP3
    # --------------------------------------------------------

    log_message("Conversion MP3")

    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            str(WAV_TMP),
            "-ac",
            "1",
            "-ar",
            "22050",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "48k",
            str(MP3_TMP),
        ],
        check=True,
        timeout=60,
    )

    if not MP3_TMP.is_file() or MP3_TMP.stat().st_size == 0:
        raise RuntimeError("MP3 non généré ou vide")

    MP3_TMP.replace(MP3)

    # Sauvegarder le texte après la réussite de l'audio.
    (ROOT / "phrase.txt").write_text(
        phrase,
        encoding="utf-8",
    )

    # Conserver aussi le nom utilisé par votre ancien script.
    (ROOT / "bulletin.txt").write_text(
        phrase,
        encoding="utf-8",
    )

    taille = round(MP3.stat().st_size / 1024)
    log_message(f"MP3 généré avec succès ({taille} Ko)")
    log_message("===== FIN NORMALE =====")


if __name__ == "__main__":
    try:
        main()
    except Exception as erreur:
        log_message(f"ERREUR : {erreur}")
        log_message("===== FIN EN ERREUR =====")
        raise
