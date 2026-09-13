import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from retrieval.jina_client import JinaEmbedder, JinaReranker, JinaTokenTracker
from retrieval.schemas import RetrievedChunk


def create_sample_chunk(content: str, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content=content,
        score=score,
        vector_score=score,
        keyword_score=score,
        source_url="https://ecajmer.ac.in/notices/sample.pdf",
        last_verified=datetime.now(UTC),
        token_count=40,
        department="CSE",
        owner="Exam Cell",
    )


def test_jina_token_tracker() -> None:
    tracker = JinaTokenTracker()
    tracker.reset()

    tracker.record_usage("embeddings", 500)
    tracker.record_usage("reranker", 300)

    summary = tracker.get_summary()
    assert summary["embeddings_tokens"] == 500
    assert summary["reranker_tokens"] == 300
    assert summary["total_tokens"] == 800
    assert summary["free_tier_limit"] == 10_000_000
    assert summary["free_tier_remaining"] == 10_000_000 - 800
    assert summary["free_tier_used_pct"] == pytest.approx(0.008, rel=1e-2)


@pytest.mark.asyncio
async def test_jina_embedder_batching_and_payload() -> None:
    embedder = JinaEmbedder(api_key="mock-jina-key", model="jina-embeddings-v3", batch_size=32)
    assert embedder.is_available() is True

    # 70 texts should result in 3 batches: 32, 32, 6
    texts = [f"Text chunk number {i}" for i in range(70)]

    mock_post = AsyncMock()

    def mock_post_side_effect(url, headers, json):
        batch_len = len(json["input"])
        mock_resp = AsyncMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "model": "jina-embeddings-v3",
            "data": [{"embedding": [0.1] * 1024, "index": i} for i in range(batch_len)],
            "usage": {"total_tokens": batch_len * 15},
        }
        return mock_resp

    mock_post.side_effect = mock_post_side_effect

    with patch("httpx.AsyncClient.post", mock_post):
        embeddings = await embedder.aembed_texts(texts, task="retrieval.passage")

    assert len(embeddings) == 70
    assert len(embeddings[0]) == 1024
    assert mock_post.call_count == 3

    # Check payload parameters of first call
    first_call_args = mock_post.call_args_list[0]
    call_json = first_call_args.kwargs["json"]
    assert call_json["model"] == "jina-embeddings-v3"
    assert call_json["task"] == "retrieval.passage"
    assert call_json["dimensions"] == 1024
    assert len(call_json["input"]) == 32


@pytest.mark.asyncio
async def test_jina_embedder_query_task() -> None:
    embedder = JinaEmbedder(api_key="mock-jina-key")

    mock_post = AsyncMock()
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "model": "jina-embeddings-v3",
        "data": [{"embedding": [0.5] * 1024, "index": 0}],
        "usage": {"total_tokens": 12},
    }
    mock_post.return_value = mock_resp

    with patch("httpx.AsyncClient.post", mock_post):
        query_vec = await embedder.aembed_query("mid term exam schedule")

    assert len(query_vec) == 1024
    call_json = mock_post.call_args.kwargs["json"]
    assert call_json["task"] == "retrieval.query"
    assert call_json["input"] == ["mid term exam schedule"]


@pytest.mark.asyncio
async def test_jina_embedder_retry_on_429() -> None:
    embedder = JinaEmbedder(api_key="mock-jina-key", max_retries=3)

    mock_post = AsyncMock()

    # First attempt: 429 Too Many Requests
    resp_429 = httpx.Response(status_code=429, request=httpx.Request("POST", embedder.API_URL))
    err_429 = httpx.HTTPStatusError("Rate limited", request=resp_429.request, response=resp_429)

    # Second attempt: 200 OK
    resp_200 = AsyncMock(spec=httpx.Response)
    resp_200.status_code = 200
    resp_200.raise_for_status = MagicMock()
    resp_200.json.return_value = {
        "model": "jina-embeddings-v3",
        "data": [{"embedding": [0.2] * 1024, "index": 0}],
        "usage": {"total_tokens": 20},
    }

    mock_post.side_effect = [err_429, resp_200]

    with patch("httpx.AsyncClient.post", mock_post), patch("asyncio.sleep", AsyncMock()):
        result = await embedder.aembed_texts(["sample text"])

    assert len(result) == 1
    assert len(result[0]) == 1024
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_jina_reranker_success() -> None:
    reranker = JinaReranker(api_key="mock-jina-key", model="jina-reranker-v2-base-multilingual")
    assert reranker.is_available() is True

    c1 = create_sample_chunk("Chunk 1: General college fees notice")
    c2 = create_sample_chunk("Chunk 2: Semester 7 mid term exam schedule table")

    mock_post = AsyncMock()
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "model": "jina-reranker-v2-base-multilingual",
        "results": [
            {"index": 1, "relevance_score": 0.94},  # c2 should be rank 1
            {"index": 0, "relevance_score": 0.35},  # c1 should be rank 2
        ],
        "usage": {"total_tokens": 85},
    }
    mock_post.return_value = mock_resp

    with patch("httpx.AsyncClient.post", mock_post):
        results = await reranker.arerank(
            query="when is sem 7 exam",
            chunks=[c1, c2],
            top_n=2,
        )

    assert len(results) == 2
    assert results[0].content == c2.content
    assert results[0].rank == 1
    assert results[0].rerank_score == 0.94
    assert results[1].content == c1.content
    assert results[1].rank == 2
    assert results[1].rerank_score == 0.35

    # Check payload parameters
    call_json = mock_post.call_args.kwargs["json"]
    assert call_json["model"] == "jina-reranker-v2-base-multilingual"
    assert call_json["query"] == "when is sem 7 exam"
    assert call_json["top_n"] == 2
    assert len(call_json["documents"]) == 2


@pytest.mark.asyncio
async def test_jina_reranker_missing_key() -> None:
    reranker = JinaReranker(api_key="")
    assert reranker.is_available() is False

    c1 = create_sample_chunk("Chunk 1")
    with pytest.raises(ValueError, match="JINA_API_KEY is not configured"):
        await reranker.arerank(query="test", chunks=[c1], top_n=1)


@pytest.mark.asyncio
async def test_jina_reader() -> None:
    from retrieval.jina_client import JinaReader

    reader = JinaReader(api_key="mock-key")
    mock_get = AsyncMock()
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = "# Engineering College Ajmer\n\nOfficial notice content."
    mock_get.return_value = mock_resp

    with patch("httpx.AsyncClient.get", mock_get):
        md_text = await reader.read_url("https://ecajmer.ac.in/circulars")

    assert "Engineering College Ajmer" in md_text
    assert mock_get.call_args[0][0] == "https://r.jina.ai/https://ecajmer.ac.in/circulars"
