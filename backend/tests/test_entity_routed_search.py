import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from retrieval.hybrid_search import HybridSearcher
from retrieval.schemas import RetrievedChunk


def create_sample_chunk(
    chunk_id: uuid.UUID | None = None,
    content: str = "Sample content",
    department: str = "Computer Science and Engineering",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        score=0.8,
        vector_score=0.8,
        keyword_score=0.8,
        source_url="https://ecajmer.ac.in/notices/sample.pdf",
        last_verified=datetime.now(UTC),
        token_count=50,
        department=department,
        owner="Notice Cell",
    )


@pytest.mark.asyncio
async def test_entity_routed_search_with_department_intent() -> None:
    """Test that student queries mentioning a department route with department filters."""
    mock_session = AsyncMock()
    mock_vector_searcher = AsyncMock()
    mock_keyword_searcher = AsyncMock()

    cse_chunk = create_sample_chunk(
        content="CSE III Sem Midterm Timetable",
        department="Computer Science and Engineering",
    )

    mock_vector_searcher.search.return_value = [cse_chunk]
    mock_keyword_searcher.search.return_value = [cse_chunk]

    hybrid = HybridSearcher(
        vector_searcher=mock_vector_searcher,
        keyword_searcher=mock_keyword_searcher,
    )

    # Query with "cse" intent
    results = await hybrid.search(
        session=mock_session,
        query="what is the cse 3rd sem schedule",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].department == "Computer Science and Engineering"

    # Verify vector searcher was called with detected department filter
    mock_vector_searcher.search.assert_called_once()
    call_kwargs = mock_vector_searcher.search.call_args.kwargs
    assert "Computer Science and Engineering" in call_kwargs.get("departments", [])


@pytest.mark.asyncio
async def test_intent_routed_search_fallback_when_zero_results() -> None:
    """Test that if filtered search returns 0 results, it falls back to unconstrained search."""
    mock_session = AsyncMock()
    mock_vector_searcher = AsyncMock()
    mock_keyword_searcher = AsyncMock()

    general_notice_chunk = create_sample_chunk(
        content="All students id card mandatory rules",
        department="Proctor Section",
    )

    # First attempt (with filter) returns empty; second attempt (unfiltered fallback) returns the notice
    mock_vector_searcher.search.side_effect = [
        [],  # Filtered call returns 0
        [general_notice_chunk],  # Fallback call returns notice
    ]
    mock_keyword_searcher.search.side_effect = [
        [],  # Filtered call returns 0
        [general_notice_chunk],  # Fallback call returns notice
    ]

    hybrid = HybridSearcher(
        vector_searcher=mock_vector_searcher,
        keyword_searcher=mock_keyword_searcher,
    )

    results = await hybrid.search(
        session=mock_session,
        query="proctor section circular",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].department == "Proctor Section"

    # Verify both searches were called twice (1st: filtered, 2nd: fallback unfiltered)
    assert mock_vector_searcher.search.call_count == 2
    assert mock_keyword_searcher.search.call_count == 2

    # Second call must have departments=None
    second_call_kwargs = mock_vector_searcher.search.call_args_list[1].kwargs
    assert second_call_kwargs.get("departments") is None
