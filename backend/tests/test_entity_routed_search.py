from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from retrieval.hybrid_search import HybridSearcher
from retrieval.schemas import RetrievedChunk


def create_sample_chunk(
    content: str, department: str | None = None, score: float = 0.5
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        score=score,
        vector_score=score,
        keyword_score=score,
        source_url="https://ecajmer.ac.in/notice.pdf",
        last_verified=datetime.now(UTC),
        token_count=20,
        department=department,
    )


@pytest.mark.asyncio
async def test_entity_routed_search_with_department_intent() -> None:
    """Test that student queries mentioning a department apply a soft RRF ranking boost."""
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

    # Per Phase 1b, search is unconstrained across all notices (departments=None)
    # and department matching is applied as an RRF score boost rather than a rigid SQL WHERE
    mock_vector_searcher.search.assert_called_once()
    call_kwargs = mock_vector_searcher.search.call_args.kwargs
    assert call_kwargs.get("departments") is None


@pytest.mark.asyncio
async def test_department_intent_applies_rrf_rank_boost() -> None:
    """Test that matching department chunk receives a soft RRF boost over equal-ranked non-matching chunk."""
    mock_vector_searcher = AsyncMock()
    mock_keyword_searcher = AsyncMock()

    cse_chunk = create_sample_chunk(
        content="CSE 3rd sem timetable",
        department="Computer Science and Engineering",
    )
    general_chunk = create_sample_chunk(
        content="General circular for all branches",
        department="Registrar Section",
    )

    # General chunk ranked 1st in raw vector search, CSE chunk ranked 2nd
    mock_vector_searcher.search.return_value = [general_chunk, cse_chunk]
    mock_keyword_searcher.search.return_value = [general_chunk, cse_chunk]

    hybrid = HybridSearcher(
        vector_searcher=mock_vector_searcher,
        keyword_searcher=mock_keyword_searcher,
    )

    # In reciprocal_rank_fusion with target_departments=["Computer Science and Engineering"],
    # CSE chunk receives dept_boost multiplier (1.3x)
    fused = hybrid.reciprocal_rank_fusion(
        vector_results=[general_chunk, cse_chunk],
        keyword_results=[general_chunk, cse_chunk],
        target_departments=["Computer Science and Engineering"],
        dept_boost=1.3,
    )

    # Fused score for CSE chunk should be boosted by 1.3x over general chunk
    cse_fused = next(c for c in fused if c.department == "Computer Science and Engineering")
    gen_fused = next(c for c in fused if c.department == "Registrar Section")
    assert cse_fused.score > (2.0 / (60 + 2))  # base RRF would be ~0.0322, with boost it is ~0.0419
    assert cse_fused.score > gen_fused.score
