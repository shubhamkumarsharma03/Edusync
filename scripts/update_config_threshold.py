with open("backend/api/config.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    'CONFIDENCE_THRESHOLD: float = 0.55',
    'CONFIDENCE_THRESHOLD: float = 0.40'
)

with open("backend/api/config.py", "w", encoding="utf-8") as f:
    f.write(text)

print("backend/api/config.py updated with CONFIDENCE_THRESHOLD = 0.40")

