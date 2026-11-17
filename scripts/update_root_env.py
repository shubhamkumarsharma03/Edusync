with open(".env", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("CONFIDENCE_THRESHOLD=0.55", "CONFIDENCE_THRESHOLD=0.40")

with open(".env", "w", encoding="utf-8") as f:
    f.write(text)

print("Root .env updated with CONFIDENCE_THRESHOLD=0.40")

