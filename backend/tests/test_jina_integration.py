import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from ingestion.embedder import DocumentEmbedder
from retrieval.jina_client import jina_token_tracker
from retrieval.reranker import CrossEncoderReranker
from retrieval.schemas import RetrievedChunk


@pytest.mark.asyncio
async def test_embedder_jina_routing() -> None:
    """Test that DocumentEmbedder routes to Jina when provider is configured and available."""
    with (
        patch("retrieval.jina_client.JinaEmbedder.is_available", return_value=True),
        patch(
            "retrieval.jina_client.JinaEmbedder.aembed_texts",
            new_callable=AsyncMock,
            return_value=[[0.7] * 1024],
        ) as mock_aembed,
    ):
        embedder = DocumentEmbedder(provider="jina")
        assert embedder.jina_embedder is not None

        vectors = await embedder.aembed_texts(["sample text"], task="retrieval.passage")
        assert len(vectors) == 1
        assert len(vectors[0]) == 1024
        mock_aembed.assert_awaited_once_with(["sample text"], task="retrieval.passage")


@pytest.mark.asyncio
async def test_reranker_jina_routing() -> None:
    """Test that CrossEncoderReranker routes to Jina when provider is configured and available."""
    dummy_chunk = RetrievedChunk(
        chunk_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        document_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        content="Important notice about exams",
        score=0.5,
        source_url="https://ecajmer.ac.in/notices/exam.pdf",
        last_verified=datetime.now(UTC),
        token_count=35,
    )

    with (
        patch("retrieval.jina_client.JinaReranker.is_available", return_value=True),
        patch(
            "retrieval.jina_client.JinaReranker.arerank",
            new_callable=AsyncMock,
            return_value=[dummy_chunk],
        ) as mock_arerank,
    ):
        reranker = CrossEncoderReranker(provider="jina")
        assert reranker.jina_reranker is not None

        results = await reranker.arerank(
            query="exam timetable",
            chunks=[dummy_chunk],
            top_k=5,
        )
        assert len(results) == 1
        mock_arerank.assert_awaited_once_with(
            query="exam timetable",
            chunks=[dummy_chunk],
            top_n=5,
        )


@pytest.mark.asyncio
async def test_admin_jina_usage_endpoint() -> None:
    """Test that /admin/jina-usage endpoint reports current tracker statistics accurately."""
    jina_token_tracker.reset()
    jina_token_tracker.record_usage("embeddings", 1200)
    jina_token_tracker.record_usage("reranker", 800)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.get("/admin/jina-usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["embeddings_tokens"] == 1200
        assert data["reranker_tokens"] == 800
        assert data["total_tokens"] == 2000
        assert data["free_tier_limit"] == 10_000_000
        assert data["free_tier_remaining"] == 9_998_000
        assert data["free_tier_used_pct"] == 0.02
