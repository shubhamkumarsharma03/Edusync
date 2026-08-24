import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from retrieval.hybrid_search import HybridSearcher
from retrieval.reranker import CrossEncoderReranker
from retrieval.schemas import RetrievedChunk


def create_sample_chunk(
    content: str,
    score: float = 0.5,
    vector_score: float | None = None,
    keyword_score: float | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        score=score,
        vector_score=vector_score,
        keyword_score=keyword_score,
        source_url="https://ecajmer.ac.in/notices/sample.pdf",
        last_verified=datetime.now(UTC),
        token_count=40,
        department="CSE",
        owner="Exam Cell",
    )


def test_sigmoid_normalization() -> None:
    """Test that sigmoid mapping correctly normalizes logits into [0, 1]."""
    assert pytest.approx(CrossEncoderReranker.sigmoid(0.0), rel=1e-3) == 0.5
    assert CrossEncoderReranker.sigmoid(100.0) > 0.999
    assert CrossEncoderReranker.sigmoid(-100.0) < 0.001
    assert 0.0 <= CrossEncoderReranker.sigmoid(2.5) <= 1.0


def test_reranker_sorting_and_ranking() -> None:
    """Test that CrossEncoderReranker predicts scores, applies sigmoid, and sorts descending."""
    mock_model = MagicMock()
    # c2 has highest score, c1 medium, c3 negative
    mock_model.predict.return_value = [-0.5, 4.2, -3.1]
    reranker = CrossEncoderReranker(model=mock_model)

    c1 = create_sample_chunk("Chunk 1: general college info")
    c2 = create_sample_chunk("Chunk 2: exact mid term schedule dates")
    c3 = create_sample_chunk("Chunk 3: unrelated sports news")

    results = reranker.rerank(
        query="when are the mid term exams",
        chunks=[c1, c2, c3],
        top_k=3,
    )

    assert len(results) == 3
    # Top ranked chunk must be c2
    assert results[0].content == c2.content
    assert results[0].rank == 1
    assert results[0].rerank_score > results[1].rerank_score > results[2].rerank_score
    assert pytest.approx(results[0].score, rel=1e-3) == CrossEncoderReranker.sigmoid(4.2)
    assert pytest.approx(results[1].score, rel=1e-3) == CrossEncoderReranker.sigmoid(-0.5)
    assert pytest.approx(results[2].score, rel=1e-3) == CrossEncoderReranker.sigmoid(-3.1)


def test_top_k_truncation() -> None:
    """Test that reranker respects the top_k parameter."""
    mock_model = MagicMock()
    mock_model.predict.return_value = list(range(10))
    reranker = CrossEncoderReranker(model=mock_model)

    chunks = [create_sample_chunk(f"Content {i}") for i in range(10)]

    results = reranker.rerank(
        query="test query",
        chunks=chunks,
        top_k=4,
    )

    assert len(results) == 4
    assert [r.rank for r in results] == [1, 2, 3, 4]


def test_empty_and_blank_query() -> None:
    """Test edge cases with empty candidate lists or blank queries."""
    reranker = CrossEncoderReranker()

    # Empty candidate chunks
    assert reranker.rerank("some query", [], top_k=5) == []

    # Whitespace-only query
    chunks = [create_sample_chunk("Notice 1"), create_sample_chunk("Notice 2")]
    results = reranker.rerank("   ", chunks, top_k=2)
    assert len(results) == 2
    assert results[0].content == "Notice 1"


def test_hybrid_search_to_rerank_pipeline() -> None:
    """Test integration flow from HybridSearcher RRF fusion to CrossEncoder reranking."""
    hybrid = HybridSearcher(rrf_k=60)
    mock_model = MagicMock()
    # c_distractor gets low score, c_relevant gets high score
    mock_model.predict.return_value = [0.1, 3.8]
    reranker = CrossEncoderReranker(model=mock_model)

    c_relevant = create_sample_chunk("Mid term exam timetable for Semester 7 CSE")
    c_distractor = create_sample_chunk("Semester 7 fee deposit circular")

    # Suppose keyword search retrieved both, vector retrieved c_distractor
    vector_results = [c_distractor]
    keyword_results = [c_distractor, c_relevant]

    # Hybrid RRF would rank c_distractor #1 because it appeared in both
    merged = hybrid.reciprocal_rank_fusion(vector_results, keyword_results, top_k=5)
    assert merged[0].content == c_distractor.content

    # Now rerank with cross-encoder which recognizes c_relevant is actually more relevant to "timetable"
    reranked = reranker.rerank("when is the CSE sem 7 timetable", merged, top_k=5)

    # Reranker should elevate c_relevant to rank 1
    assert reranked[0].content == c_relevant.content
    assert reranked[0].rank == 1
    assert reranked[0].rerank_score > reranked[1].rerank_score
