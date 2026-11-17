with open("backend/retrieval/query_normalizer.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '"Examination Section": ["exam", "examination"]'
replacement = '"Examination Section": ["examination section", "exam cell", "exam branch"]'

assert target in text
new_text = text.replace(target, replacement)
with open("backend/retrieval/query_normalizer.py", "w", encoding="utf-8") as f:
    f.write(new_text)

print("query_normalizer.py updated: Examination Section requires specific department terminology!")

