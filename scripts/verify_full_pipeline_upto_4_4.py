"""End-to-End Pipeline Verification Script (Up to Phase 4.4).

Demonstrates the entire EduSync pipeline:
1. Sample Institutional Document Chunks (Phase 3 Ingestion output)
2. Cross-Encoder Reranking (Phase 4.2)
3. Confidence Gate & Fallback Check (Phase 4.3)
4. Grounded LLM Generation & Source Citations (Phase 4.4)
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from retrieval.confidence_gate import ConfidenceGate
from retrieval.generator import LLMGenerator
from retrieval.reranker import CrossEncoderReranker
from retrieval.schemas import RetrievedChunk

# Sample institutional documents reflecting real college circulars
SAMPLE_CHUNKS = [
    RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="B.Tech Semester 7 Mid-Term Examinations will commence from Sept 15, 2026. All students must bring their physical college ID cards to the examination hall. Mobile phones and smart watches are strictly prohibited.",
        score=0.70,
        source_url="https://ecajmer.ac.in/notices/exam_schedule_sem7.pdf",
        last_verified=datetime.now(UTC),
        token_count=35,
        department="Examination",
        owner="Controller of Examinations",
    ),
    RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="The last date for depositing the odd semester tuition and hostel fee is August 30, 2026. A late fee penalty of Rs 50/day applies afterwards. Fee can be paid via the online portal.",
        score=0.65,
        source_url="https://ecajmer.ac.in/notices/fee_submission_2026.html",
        last_verified=datetime.now(UTC),
        token_count=32,
        department="Accounts",
        owner="Accounts Section",
    ),
    RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="Syllabus for CS-702 Machine Learning includes Supervised Learning algorithms, Deep Neural Networks, Transformer models, and Reinforcement Learning with practical lab assignments.",
        score=0.60,
        source_url="https://ecajmer.ac.in/departments/cs/syllabus_btech.pdf",
        last_verified=datetime.now(UTC),
        token_count=28,
        department="CS/IT",
        owner="HOD Computer Science",
    ),
]


async def run_pipeline_for_query(query: str, test_title: str):
    print("\n" + "=" * 80)
    print(f"QUERY TEST: {test_title}")
    print(f"User Query: \"{query}\"")
    print("=" * 80)

    # 1. Reranking (Phase 4.2)
    reranker = CrossEncoderReranker()
    print("\n[Step 1: Cross-Encoder Reranking]")
    reranked = reranker.rerank(query=query, chunks=SAMPLE_CHUNKS, top_k=3)
    for idx, c in enumerate(reranked, start=1):
        print(f"  Rank #{idx} [Score: {c.rerank_score:.4f}] Dept: {c.department} | Excerpt: {c.content[:65]}...")

    # 2. Confidence Gate (Phase 4.3)
    gate = ConfidenceGate(threshold=0.55)
    print("\n[Step 2: Confidence Gate Evaluation]")
    gate_result = gate.evaluate(reranked)
    print(f"  Passed Gate:       {gate_result.passed}")
    print(f"  Top Score:         {gate_result.top_score:.4f}")
    print(f"  Confidence Level:  {gate_result.confidence_level.value.upper()}")

    # 3. LLM Generation & Citations (Phase 4.4)
    generator = LLMGenerator()
    print("\n[Step 3: Grounded Answer Generation & Citations]")
    if gate_result.passed:
        gen_result = await generator.generate_answer(
            query=query,
            chunks=gate_result.qualifying_chunks,
            confidence=gate_result.top_score,
        )
    else:
        # If gate failed, return standardized fallback response without calling LLM
        gen_result = await generator.generate_answer(
            query=query,
            chunks=[],
            confidence=gate_result.top_score,
        )

    print("\n" + "-" * 40 + " FINAL RESPONSE " + "-" * 40)
    print(f"Answer:\n{gen_result.answer}\n")
    print(f"Confidence Score: {gen_result.confidence}")
    print(f"Is Fallback:      {gen_result.is_fallback}")
    print(f"Sources Attached: ({len(gen_result.sources)})")
    for s in gen_result.sources:
        print(f"  - Document: {s.document}")
        print(f"    URL:      {s.url}")
        print(f"    Verified: {s.last_verified}")
    print("-" * 96)


async def main():
    # Test 1: In-scope Examination Question
    await run_pipeline_for_query(
        query="When do 7th semester mid-term exams start and what must students bring?",
        test_title="In-Scope: 7th Sem Mid-Term Exams Schedule",
    )

    # Test 2: In-scope Accounts Question
    await run_pipeline_for_query(
        query="What is the deadline for tuition fee submission and what is the late fee fine?",
        test_title="In-Scope: Tuition Fee Submission Deadline",
    )

    # Test 3: Out-of-scope / Unverified Question
    await run_pipeline_for_query(
        query="What are the hostel rules regarding keeping pets?",
        test_title="Out-of-Scope: Unverified Query (Trust Layer Test)",
    )


if __name__ == "__main__":
    asyncio.run(main())
