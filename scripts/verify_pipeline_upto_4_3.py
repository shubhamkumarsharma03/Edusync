"""End-to-End Pipeline Verification Script (Up to Phase 4.3).

Demonstrates:
1. Hybrid Search simulation with sample institutional chunks
2. Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2)
3. Confidence Gating & Fallback evaluation
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from retrieval.confidence_gate import ConfidenceGate
from retrieval.reranker import CrossEncoderReranker
from retrieval.schemas import RetrievedChunk

# Sample institutional chunks (as produced by Phase 3 ingestion)
SAMPLE_CHUNKS = [
    RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="B.Tech Semester 7 Mid-Term Examinations will commence from Sept 15, 2026. All students must bring their physical college ID cards to the examination hall.",
        score=0.70,
        source_url="https://ecajmer.ac.in/notices/exam_schedule_sem7.pdf",
        last_verified=datetime.now(UTC),
        token_count=30,
        department="Examination",
        owner="Controller of Examinations",
    ),
    RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="The last date for depositing the odd semester tuition and hostel fee is August 30, 2026. A late fee penalty of Rs 50/day applies afterwards.",
        score=0.65,
        source_url="https://ecajmer.ac.in/notices/fee_submission_2026.html",
        last_verified=datetime.now(UTC),
        token_count=28,
        department="Accounts",
        owner="Accounts Section",
    ),
    RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="Syllabus for CS-702 Machine Learning includes Supervised Learning algorithms, Deep Neural Networks, Transformer models, and Reinforcement Learning.",
        score=0.60,
        source_url="https://ecajmer.ac.in/departments/cs/syllabus_btech.pdf",
        last_verified=datetime.now(UTC),
        token_count=25,
        department="CS/IT",
        owner="HOD Computer Science",
    ),
]


def test_query(query_text: str, description: str):
    print("\n" + "=" * 70)
    print(f"TEST CASE: {description}")
    print(f"Query: \"{query_text}\"")
    print("=" * 70)

    # 1. Cross-Encoder Reranker (Phase 4.2)
    reranker = CrossEncoderReranker()
    print("\n[Step 1] Running Cross-Encoder Reranker...")
    reranked = reranker.rerank(query=query_text, chunks=SAMPLE_CHUNKS, top_k=3)

    for idx, c in enumerate(reranked, start=1):
        print(f"  {idx}. [Score: {c.rerank_score:.4f}] Dept: {c.department} | Content: {c.content[:70]}...")

    # 2. Confidence Gate (Phase 4.3)
    gate = ConfidenceGate(threshold=0.55)
    print("\n[Step 2] Evaluating through Confidence Gate (Threshold: 0.55)...")
    result = gate.evaluate(reranked)

    print(f"  Passed Gate:       {result.passed}")
    print(f"  Top Score:         {result.top_score:.4f}")
    print(f"  Confidence Level:  {result.confidence_level.value.upper()}")

    if result.passed:
        print(f"  Qualifying Chunks: {len(result.qualifying_chunks)}")
        print("  --> STATUS: SUCCESS! Safe to send to LLM for grounded answer generation.")
    else:
        print(f"  Fallback Message:  \"{result.fallback_message}\"")
        print("  --> STATUS: BLOCKED! LLM call avoided to prevent hallucinations.")


def main():
    # Case 1: In-scope relevant query
    test_query(
        query_text="When are the 7th semester mid term exams starting?",
        description="Relevant College Query (Should PASS Confidence Gate)",
    )

    # Case 2: In-scope fees query
    test_query(
        query_text="What is the deadline for tuition fee payment?",
        description="Relevant Fee Notice Query (Should PASS Confidence Gate)",
    )

    # Case 3: Out-of-scope irrevelant query
    test_query(
        query_text="How do I bake a chocolate cake at home?",
        description="Out-of-Scope Query (Should FAIL Confidence Gate and return Fallback)",
    )


if __name__ == "__main__":
    main()
