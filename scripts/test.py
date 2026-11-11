from datetime import datetime

with open("message.txt", "w", encoding="utf-8") as f:
    f.write(
        f"Bonjour depuis GitHub Actions\n"
        f"{datetime.now()}\n"
    )

print("message.txt créé")
