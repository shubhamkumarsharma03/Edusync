with open("backend/models/chunk.py", "r", encoding="utf-8") as f:
    text = f.read()

target = "    content: Mapped[str] = mapped_column(Text, nullable=False)"
replacement = """    content: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)"""

assert target in text
new_text = text.replace(target, replacement)
with open("backend/models/chunk.py", "w", encoding="utf-8") as f:
    f.write(new_text)

print("backend/models/chunk.py updated with original_content")

