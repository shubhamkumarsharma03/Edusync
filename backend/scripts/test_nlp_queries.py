import asyncio

import httpx


async def test_short_queries():
    queries = [
        "it 3rd sem tt",
        "mtech timetable",
        "cyber 5th sem",
        "oops lab room",
        "ce ca timetable",
    ]
    async with httpx.AsyncClient(timeout=60.0) as client:
        for q in queries:
            try:
                resp = await client.post("http://localhost:8000/chat", json={"query": q})
                data = resp.json()
                score = data.get("confidence_score") or 0.0
                fallback = data.get("is_fallback")
                conf = data.get("confidence")
                ans = (data.get("answer") or "")[:150].replace("\n", " ")
                sources = [s.get("title", "") for s in data.get("sources", [])]
                print(f"QUERY: '{q}'")
                print(f"  Confidence: {conf} (Score: {score:.4f}) | Fallback: {fallback}")
                print(f"  Sources: {sources}")
                print(f"  Answer: {ans}...\n")
            except Exception as e:
                print(f"Error on '{q}': {e}")


if __name__ == "__main__":
    asyncio.run(test_short_queries())
