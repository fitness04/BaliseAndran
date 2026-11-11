from datetime import datetime

texte = f"""
Balise Andran

Essai GitHub Actions

Date :
{datetime.now()}
"""

with open(
    "bulletin.txt",
    "w",
    encoding="utf-8") as f:
    f.write(texte)

print("bulletin.txt généré")
