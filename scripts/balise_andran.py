from datetime import datetime

bulletin = f"""
BALISE ANDRAN

Bulletin expérimental

Date :
{datetime.now()}

Vérification du fonctionnement
GitHub Actions.

Fin de bulletin.
"""

with open(
    "bulletin.txt",
    "w",
    encoding="utf-8") as f:
    f.write(bulletin)

print("bulletin.txt généré")
