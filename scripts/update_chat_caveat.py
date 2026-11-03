with open("backend/api/routes/chat.py", "r", encoding="utf-8") as f:
    text = f.read()

target = "    answer_text = await generate_llm_answer_async(query, combined_context)"
replacement = """    answer_text = await generate_llm_answer_async(query, combined_context)
    if gate_result.caveat:
        answer_text = f"{answer_text}\\n\\n> ⚠️ *{gate_result.caveat}*\""""

assert target in text
new_text = text.replace(target, replacement)
with open("backend/api/routes/chat.py", "w", encoding="utf-8") as f:
    f.write(new_text)
print("Updated chat.py with caveat support successfully")

