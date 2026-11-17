with open("backend/retrieval/query_normalizer.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix ACRONYM_MAP
text = text.replace(
    're.compile(r"\\b(it|i\\.t\\.)\\b", re.IGNORECASE)',
    're.compile(r"\\b(i\\.t\\.|information\\s+technology|b\\.?tech\\s+it|it\\s+dept|it\\s+branch)\\b|\\bIT\\b")'
)
text = text.replace(
    're.compile(r"\\b(me|mech|mechanical)\\b", re.IGNORECASE)',
    're.compile(r"\\b(mech|mechanical|b\\.?tech\\s+me|me\\s+dept|me\\s+branch)\\b|\\bME\\b")'
)
text = text.replace(
    're.compile(r"\\bde\\b", re.IGNORECASE)',
    're.compile(r"\\b(digital\\s+electronics)\\b|\\bDE\\b")'
)

# Fix DEPARTMENT_DETECTION
text = text.replace(
    '"Information Technology": ["it", "information technology"]',
    '"Information Technology": ["information technology", "info tech", "btech it", "it dept"]'
)
text = text.replace(
    '"Mechanical Engineering": ["me", "mech", "mechanical"]',
    '"Mechanical Engineering": ["mech", "mechanical", "btech me", "me dept"]'
)
text = text.replace(
    '"Registrar Section": ["registrar", "order", "admin"]',
    '"Registrar Section": ["registrar", "office order", "admin"]'
)

# Fix kw_clean
text = text.replace(
    'kw_clean = re.sub(r"\\bit\\b", "Information Technology", kw_clean, flags=re.IGNORECASE)',
    'kw_clean = re.sub(r"\\b(i\\.t\\.|information technology)\\b|\\bIT\\b", "Information Technology", kw_clean)'
)

with open("backend/retrieval/query_normalizer.py", "w", encoding="utf-8") as f:
    f.write(text)

print("query_normalizer.py fixed cleanly!")

