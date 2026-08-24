import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from retrieval.hybrid_search import HybridSearcher
from retrieval.keyword_search import KeywordSearcher
from retrieval.schemas import RetrievedChunk
from retrieval.vector_search import VectorSearcher


def create_sample_chunk(
    chunk_id: uuid.UUID | None = None,
    content: str = "Sample content",
    score: float = 0.8,
    vector_score: float | None = None,
    keyword_score: float | None = None,
    department: str = "CSE",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        score=score,
        vector_score=vector_score,
        keyword_score=keyword_score,
        source_url="https://ecajmer.ac.in/notices/exam.pdf",
        last_verified=datetime.now(UTC),
        token_count=50,
        department=department,
        owner="Exam Cell",
    )


def test_rrf_merge_and_deduplication() -> None:
    """Test that Reciprocal Rank Fusion correctly merges and deduplicates overlapping search results."""
    searcher = HybridSearcher(rrf_k=60)

    shared_id = uuid.uuid4()
    vector_only_id = uuid.uuid4()
    keyword_only_id = uuid.uuid4()

    vector_results = [
        create_sample_chunk(chunk_id=shared_id, content="Mid term exam notice", vector_score=0.95),
        create_sample_chunk(
            chunk_id=vector_only_id, content="Semester fee schedule", vector_score=0.80
        ),
    ]

    keyword_results = [
        create_sample_chunk(chunk_id=shared_id, content="Mid term exam notice", keyword_score=0.75),
        create_sample_chunk(
            chunk_id=keyword_only_id, content="Hostel admission circular", keyword_score=0.60
        ),
    ]

    merged = searcher.reciprocal_rank_fusion(vector_results, keyword_results, top_k=10)

    # Must contain exactly 3 unique chunks (shared_id was deduplicated)
    assert len(merged) == 3

    # Shared chunk should be ranked #1 because it appeared in both rank-1 positions
    assert merged[0].chunk_id == shared_id
    assert merged[0].rank == 1
    assert merged[0].vector_score == 0.95
    assert merged[0].keyword_score == 0.75

    # RRF score for shared chunk: 1/(60+1) + 1/(60+1) = 2/61 ~ 0.03278
    expected_shared_score = (1.0 / 61.0) + (1.0 / 61.0)
    assert pytest.approx(merged[0].score, rel=1e-3) == expected_shared_score

    # Second and third items should be the single-source chunks
    merged_ids = [c.chunk_id for c in merged]
    assert vector_only_id in merged_ids
    assert keyword_only_id in merged_ids


def test_bm25_in_memory_scorer() -> None:
    """Test in-memory BM25Okapi scoring across a collection of candidate chunks."""
    c1 = create_sample_chunk(content="The mid term examination begins on 14 September 2026.")
    c2 = create_sample_chunk(content="Hostel fee payment deadline is extended to October 2026.")
    c3 = create_sample_chunk(content="B.Tech Computer Science semester 7 syllabus for 2026.")

    query = "mid term examination"
    ranked = KeywordSearcher.score_chunks_with_bm25(query=query, chunks=[c1, c2, c3], top_k=3)

    assert len(ranked) == 3
    # First item should be the exact match for examination
    assert ranked[0].content == c1.content
    assert ranked[0].score > ranked[1].score
    assert ranked[0].rank == 1


@pytest.mark.asyncio
async def test_vector_search_execution_and_status_filtering() -> None:
    """Test that VectorSearcher translates query embedding and enforces fresh document filter."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_row = MagicMock()
    mock_row.id = chunk_id
    mock_row.document_id = doc_id
    mock_row.content = "RTU Exam Schedule 2026"
    mock_row.token_count = 60
    mock_row.last_verified = datetime.now(UTC)
    mock_row.source_url = "https://ecajmer.ac.in/exams.pdf"
    mock_row.department = "ECE"
    mock_row.owner = "Exam Cell"
    mock_row.distance = 0.15  # Cosine distance = 0.15 -> Similarity = 0.85

    mock_result.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    mock_embedder = MagicMock()
    mock_embedder.embed_texts.return_value = [[0.1] * 384]

    searcher = VectorSearcher(embedder=mock_embedder)
    results = await searcher.search(
        session=mock_session,
        query="when are the exams",
        top_k=5,
        allowed_statuses=["fresh"],
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_id
    assert pytest.approx(results[0].vector_score, rel=1e-3) == 0.85
    assert pytest.approx(results[0].score, rel=1e-3) == 0.85
    assert results[0].department == "ECE"
    assert results[0].source_url == "https://ecajmer.ac.in/exams.pdf"
    assert mock_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_keyword_search_execution() -> None:
    """Test that KeywordSearcher queries Postgres FTS and maps returned rows correctly."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_row = MagicMock()
    mock_row.id = chunk_id
    mock_row.document_id = doc_id
    mock_row.content = "Library book return fine notice"
    mock_row.token_count = 40
    mock_row.last_verified = datetime.now(UTC)
    mock_row.source_url = "https://ecajmer.ac.in/library.pdf"
    mock_row.department = "General"
    mock_row.owner = "Librarian"
    mock_row.rank_score = 0.42

    mock_result.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    searcher = KeywordSearcher()
    results = await searcher.search(
        session=mock_session,
        query="library fine",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_id
    assert results[0].keyword_score == 0.42
    assert results[0].content == "Library book return fine notice"
    assert mock_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_hybrid_search_end_to_end() -> None:
    """Test full HybridSearcher orchestrating vector and keyword sub-searches."""
    mock_session = AsyncMock()

    mock_vector_searcher = AsyncMock()
    mock_keyword_searcher = AsyncMock()

    chunk_1 = create_sample_chunk(content="Doc 1", vector_score=0.9)
    chunk_2 = create_sample_chunk(content="Doc 2", keyword_score=0.8)

    mock_vector_searcher.search.return_value = [chunk_1]
    mock_keyword_searcher.search.return_value = [chunk_2]

    hybrid = HybridSearcher(
        vector_searcher=mock_vector_searcher,
        keyword_searcher=mock_keyword_searcher,
    )

    results = await hybrid.search(session=mock_session, query="test query", top_k=5)

    assert len(results) == 2
    assert mock_vector_searcher.search.call_count == 1
    assert mock_keyword_searcher.search.call_count == 1
