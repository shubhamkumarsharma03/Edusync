import sys
sys.path.insert(0, "backend")
import asyncio
import httpx
from api.config import get_settings

settings = get_settings()

async def test():
    prompt = """You are an institutional document QA validator for college notices.
Analyze whether the provided official notices contain direct, verified factual evidence to answer the student's question.

Return STRICT JSON with these fields:
{
  "answerable": true/false,
  "evidence": "exact quote from notices supporting the answer, or empty string if not found",
  "reason": "brief explanation"
}

NOTICES:
[Notice: BTU - Circular for B.Tech. III Sem (Main and Back Exam) Session 2026-27 (Last date 01.11.2026 with single fee)]
All students of B.Tech. III Semester are informed that BTU exam form filling for Main and Back Exam has started. Examination fee is Rs. 1600. Late fee applies after 01.11.2026.

QUESTION:
What is the fee for duplicate degree certificate from BTU Bikaner?
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        print("Status:", r.status_code)
        if r.status_code == 200:
            print(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        else:
            print(r.text)

asyncio.run(test())

