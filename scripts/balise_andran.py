import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
import requests

PIOUPIOU_ID = 2031
MAX_AGE_MINUTES = 30
SILENCE_DEBUT_MS = 500
HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent if HERE.name == "scripts" else HERE
ROOT = Path(os.environ.get("GITHUB_WORKSPACE", str(DEFAULT_ROOT))).resolve()
os.chdir(ROOT)
MODEL = os.environ.get("PIPER_MODEL", r"C:\Piper\models\model.onnx" if os.name == "nt" else str(ROOT / "models/model.onnx"))
FFMPEG = os.environ.get("FFMPEG", r"C:\ffmpeg\bin\ffmpeg.exe" if os.name == "nt" else "ffmpeg")
PIPER_CMD = [os.environ.get("PIPER", r"C:\Piper\piper.exe")] if os.name == "nt" else [sys.executable, "-m", "piper"]
LOGFILE = ROOT / "balise_andran.log"
ABSENT = "Balise de l'Andran, mesure non disponible."
DIRECTIONS = ["nord", "nord nord èst", "nord èst", "èst nord èst", "èst", "èst sud èst", "sud èst", "sud sud èst", "sud", "sud sud ouest", "sud ouest", "ouest sud ouest", "ouest", "ouest nord ouest", "nord ouest", "nord nord ouest"]

def log(message):
    if LOGFILE.exists() and LOGFILE.stat().st_size >= 100 * 1024:
        lines = LOGFILE.read_text(encoding="utf-8").splitlines(True)
        LOGFILE.write_text("".join(lines[len(lines)//2:]), encoding="utf-8")
    line = f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {message}"
    print(line, flush=True)
    with LOGFILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def audio(phrase, destination):
    wav = ROOT / "BaliseAndran_v4.wav"
    tmp = ROOT / "BaliseAndran_v4_tmp.wav"
    try:
        subprocess.run(PIPER_CMD + ["--model", MODEL, "--length_scale", "1.6", "--output_file", str(wav)], input=phrase + "\n", text=True, encoding="utf-8", check=True, timeout=120)
        subprocess.run([FFMPEG, "-y", "-i", str(wav), "-af", f"adelay={SILENCE_DEBUT_MS}:all=1", str(tmp)], check=True, timeout=60)
        subprocess.run([FFMPEG, "-y", "-i", str(tmp), "-ac", "1", "-ar", "22050", "-codec:a", "libmp3lame", "-b:a", "48k", str(destination)], check=True, timeout=60)
        if not destination.exists() or destination.stat().st_size < 512:
            raise RuntimeError("MP3 absent ou trop petit")
    finally:
        wav.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)

def atomic_text(path, value):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-message", action="store_true")
    args = parser.parse_args()
    if args.local_message:
        audio(ABSENT, ROOT / "indisponible.mp3")
        print("Message local genere : indisponible.mp3")
        return
    log("===== DEMARRAGE V4 =====")
    log(f"Dossier de travail : {ROOT}")
    now = datetime.now(timezone.utc)
    measured = 0
    valid = False
    phrase = ABSENT
    reason = "API indisponible"
    try:
        log(f"Lecture balise WindBird {PIOUPIOU_ID}")
        r = requests.get(f"http://api.pioupiou.fr/v1/live/{PIOUPIOU_ID}", timeout=(10, 15))
        r.raise_for_status()
        m = r.json()["data"]["measurements"]
        dt = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("Date de mesure sans fuseau")
        measured = int(dt.timestamp())
        age = (now - dt).total_seconds()
        heading, wind, gust = [float(m[k]) for k in ("wind_heading", "wind_speed_avg", "wind_speed_max")]
        if not all(math.isfinite(v) for v in (heading, wind, gust)):
            raise ValueError("Valeur meteo non finie")
        if not (0 <= heading <= 360 and 0 <= wind <= gust <= 500):
            raise ValueError("Valeurs meteo incoherentes")
        valid = 0 <= age <= MAX_AGE_MINUTES * 60
        reason = "VALIDE" if valid else "NON DISPONIBLE : date perimee ou future"
        log(f"Heure mesure : {dt.astimezone(timezone.utc):%d/%m/%Y %H:%M:%S UTC}")
        log(f"Age mesure = {age/60:.1f} minutes")
        log(f"Direction={heading:.0f} deg Vent={wind:.0f} km/h Rafale={gust:.0f} km/h")
        if valid:
            direction = DIRECTIONS[int(heading / 22.5 + 0.5) % 16]
            phrase = f"Balise de l'Andran, {direction}, {round(wind)} kilomètre heure, {round(gust)} maximum."
    except Exception as exc:
        valid = False
        phrase = ABSENT
        reason = f"NON DISPONIBLE : {exc}"
    log(f"Etat mesure : {reason}")
    log(f"Phrase : {phrase}")
    pending = ROOT / "BaliseAndran.pending.mp3"
    try:
        audio(phrase, pending)
        content = pending.read_bytes()
        meta = {
            "schema": 1,
            "station_id": PIOUPIOU_ID,
            "valid": valid,
            "measurement_epoch": measured,
            "generated_epoch": int(datetime.now(timezone.utc).timestamp()),
            "max_age_seconds": MAX_AGE_MINUTES * 60,
            "mp3_bytes": len(content),
            "mp3_sha256": hashlib.sha256(content).hexdigest()
        }
        os.replace(pending, ROOT / "BaliseAndran.mp3")
        atomic_text(ROOT / "phrase.txt", phrase)
        atomic_text(ROOT / "bulletin.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        log(f"MP3 genere avec succes ({len(content)} octets)")
        log(f"SHA256 : {meta['mp3_sha256']}")
        log("===== FIN NORMALE =====")
    except Exception as exc:
        log(f"ERREUR GENERATION : {exc}")
        raise
    finally:
        pending.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
