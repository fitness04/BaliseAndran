from datetime import datetime

texte = f"""
Balise Andran

Test GitHub Actions

{datetime.now()}
"""

with open("bulletin.txt", "w", encoding="utf-8") as f:
    f.write(texte)

print("bulletin généré")
