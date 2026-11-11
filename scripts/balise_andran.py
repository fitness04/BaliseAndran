import requests
from datetime import datetime, timezone

PIOUPIOU_ID = 2031

directions = [
    "nord",
    "nord nord est",
    "nord est",
    "est nord est",
    "est",
    "est sud est",
    "sud est",
    "sud sud est",
    "sud",
    "sud sud ouest",
    "sud ouest",
    "ouest sud ouest",
    "ouest",
    "ouest nord ouest",
    "nord ouest",
    "nord nord ouest"
]

url = f"http://api.pioupiou.fr/v1/live/{PIOUPIOU_ID}"

r = requests.get(url, timeout=10)
r.raise_for_status()

data = r.json()
m = data["data"]["measurements"]

cap = round(m["wind_heading"])
vent = round(m["wind_speed_avg"])
rafale = round(m["wind_speed_max"])

idx = int((cap / 22.5) + 0.5) % 16
direction = directions[idx]

phrase = (
    f"Balise de l'Andran, "
    f"{direction}, "
    f"{vent} kilomètre heure, "
    f"{rafale} maximum."
)

with open(
    "bulletin.txt",
    "w",
    encoding="utf-8"
) as f:
    f.write(phrase)

print(phrase)
