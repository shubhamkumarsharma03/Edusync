"""Jina AI API Client for EduSync RAG Pipeline.

Provides high-performance, asynchronous integration for:
- jina-embeddings-v3 (1024 dimensions, 8,192 token window, task-specific embeddings)
- jina-reranker-v2-base-multilingual (cross-encoder relevance reranking)
- JinaTokenTracker: Real-time tracking against the 10,000,000 free-tier token quota.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Sequence
from typing import Any

import httpx

from api.config import get_settings
from retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class JinaTokenTracker:
    """Thread-safe cumulative token tracker for Jina AI free-tier quota monitoring."""

    FREE_TIER_LIMIT: int = 10_000_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.embeddings_tokens: int = 0
        self.reranker_tokens: int = 0
        self.total_tokens: int = 0

    def record_usage(self, category: str, tokens: int) -> None:
        """Record token consumption and log remaining quota."""
        if tokens <= 0:
            return
        with self._lock:
            if category == "embeddings":
                self.embeddings_tokens += tokens
            elif category == "reranker":
                self.reranker_tokens += tokens
            self.total_tokens += tokens
            curr_total = self.total_tokens

        pct = (curr_total / self.FREE_TIER_LIMIT) * 100.0
        remaining = max(0, self.FREE_TIER_LIMIT - curr_total)
        logger.info(
            f"[Jina AI] Request consumed {tokens:,} tokens ({category}). "
            f"Cumulative: {curr_total:,} / {self.FREE_TIER_LIMIT:,} ({pct:.2f}% used, {remaining:,} remaining)"
        )

    def reset(self) -> None:
        """Reset counters to zero (useful for testing and quota resets)."""
        with self._lock:
            self.embeddings_tokens = 0
            self.reranker_tokens = 0
            self.total_tokens = 0

    def get_summary(self) -> dict[str, Any]:
        """Return token usage breakdown and quota statistics."""
        with self._lock:
            pct = round((self.total_tokens / self.FREE_TIER_LIMIT) * 100.0, 4)
            remaining = max(0, self.FREE_TIER_LIMIT - self.total_tokens)
            return {
                "embeddings_tokens": self.embeddings_tokens,
                "reranker_tokens": self.reranker_tokens,
                "total_tokens": self.total_tokens,
                "free_tier_limit": self.FREE_TIER_LIMIT,
                "free_tier_remaining": remaining,
                "free_tier_used_pct": pct,
                "remaining_tokens": remaining,
                "used_percentage": pct,
            }

    get_stats = get_summary


# Global singleton instance for token usage tracking
jina_token_tracker = JinaTokenTracker()


class JinaEmbedder:
    """Asynchronous client for Jina Embeddings v3 API (1024-dim, 8192 context length)."""

    API_URL: str = "https://api.jina.ai/v1/embeddings"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int = 1024,
        batch_size: int = 32,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        settings = get_settings()
        self.api_key = settings.JINA_API_KEY if api_key is None else api_key
        self.model = settings.JINA_EMBEDDING_MODEL if model is None else model
        self.dimensions = dimensions or settings.EMBEDDING_DIM
        self.batch_size = batch_size or settings.JINA_EMBED_BATCH_SIZE
        self.timeout = timeout or settings.JINA_TIMEOUT
        self.max_retries = max_retries or settings.JINA_MAX_RETRIES

    def is_available(self) -> bool:
        """Check whether a valid Jina API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    async def aembed_texts(
        self,
        texts: list[str],
        task: str = "retrieval.passage",
    ) -> list[list[float]]:
        """Asynchronously compute 1024-dimensional embeddings for a list of texts in batches.

        Args:
            texts: List of strings to embed.
            task: Jina task parameter ('retrieval.passage' for documents, 'retrieval.query' for search queries).
        """
        if not texts:
            return []

        if not self.is_available():
            raise ValueError("JINA_API_KEY is not configured in environment or settings.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.strip()}",
        }

        all_embeddings: list[list[float]] = []

        # Split into batches to respect rate limits and payload boundaries
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            payload = {
                "model": self.model,
                "task": task,
                "dimensions": self.dimensions,
                "late_chunking": False,
                "embedding_type": "float",
                "truncate": True,
                "input": batch,
            }

            # Retry loop with exponential backoff
            for attempt in range(1, self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(self.API_URL, headers=headers, json=payload)
                        resp.raise_for_status()
                        data = resp.json()

                    # Extract usage
                    usage = data.get("usage", {})
                    tokens = usage.get("total_tokens", 0)
                    jina_token_tracker.record_usage("embeddings", tokens)

                    # Sort embeddings by original index
                    items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                    batch_vectors = [item["embedding"] for item in items]
                    all_embeddings.extend(batch_vectors)
                    break

                except (httpx.HTTPStatusError, httpx.RequestError) as err:
                    status_code = (
                        getattr(err.response, "status_code", None)
                        if hasattr(err, "response") and err.response
                        else None
                    )
                    if attempt < self.max_retries and (
                        status_code in (429, 500, 502, 503, 504)
                        or isinstance(err, httpx.RequestError)
                    ):
                        backoff = 2 ** (attempt - 1) * 0.5
                        logger.warning(
                            f"[Jina Embedder] Request failed (attempt {attempt}/{self.max_retries}, "
                            f"status={status_code}): {err}. Retrying in {backoff:.1f}s..."
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            f"[Jina Embedder] Permanent error after {attempt} attempts: {err}"
                        )
                        raise

        return all_embeddings

    async def aembed_query(self, query: str) -> list[float]:
        """Convenience method to embed a single student search query with 'retrieval.query' task."""
        embeddings = await self.aembed_texts([query], task="retrieval.query")
        return embeddings[0] if embeddings else []

    def embed_texts(
        self,
        texts: list[str],
        task: str = "retrieval.passage",
    ) -> list[list[float]]:
        """Synchronous wrapper for aembed_texts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # In a running async loop, run synchronously with a dedicated thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.aembed_texts(texts, task=task))
                return future.result()
        else:
            return asyncio.run(self.aembed_texts(texts, task=task))


class JinaReranker:
    """Asynchronous client for Jina Reranker v2 API (jina-reranker-v2-base-multilingual)."""

    API_URL: str = "https://api.jina.ai/v1/rerank"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        settings = get_settings()
        self.api_key = settings.JINA_API_KEY if api_key is None else api_key
        self.model = settings.JINA_RERANKER_MODEL if model is None else model
        self.timeout = timeout or settings.JINA_TIMEOUT
        self.max_retries = max_retries or settings.JINA_MAX_RETRIES

    def is_available(self) -> bool:
        """Check whether a valid Jina API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    async def arerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        """Rerank candidate chunks using Jina Reranker v2 multilingual cross-encoder API.

        Args:
            query: The user search query.
            chunks: Candidate chunks retrieved from hybrid vector + keyword search.
            top_n: Maximum number of top relevant chunks to return.
        """
        if not chunks or not query.strip():
            return list(chunks[:top_n])

        if not self.is_available():
            raise ValueError("JINA_API_KEY is not configured in environment or settings.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.strip()}",
        }

        doc_texts = [chunk.content for chunk in chunks]
        payload = {
            "model": self.model,
            "query": query.strip(),
            "top_n": min(top_n, len(chunks)),
            "documents": doc_texts,
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(self.API_URL, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                # Track token usage
                usage = data.get("usage", {})
                tokens = usage.get("total_tokens", 0)
                jina_token_tracker.record_usage("reranker", tokens)

                results = data.get("results", [])
                reranked_chunks: list[RetrievedChunk] = []

                for rank, item in enumerate(results, start=1):
                    idx = item.get("index", 0)
                    score = float(item.get("relevance_score", 0.0))
                    if 0 <= idx < len(chunks):
                        orig_chunk = chunks[idx]
                        orig_chunk.rerank_score = score
                        orig_chunk.score = score
                        orig_chunk.rank = rank
                        reranked_chunks.append(orig_chunk)

                logger.debug(
                    f"[Jina Reranker] Reranked {len(chunks)} chunks to top {len(reranked_chunks)} items."
                )
                return reranked_chunks

            except (httpx.HTTPStatusError, httpx.RequestError) as err:
                status_code = (
                    getattr(err.response, "status_code", None)
                    if hasattr(err, "response") and err.response
                    else None
                )
                if attempt < self.max_retries and (
                    status_code in (429, 500, 502, 503, 504) or isinstance(err, httpx.RequestError)
                ):
                    backoff = 2 ** (attempt - 1) * 0.5
                    logger.warning(
                        f"[Jina Reranker] Request failed (attempt {attempt}/{self.max_retries}, "
                        f"status={status_code}): {err}. Retrying in {backoff:.1f}s..."
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"[Jina Reranker] Permanent error after {attempt} attempts: {err}")
                    raise

        return list(chunks[:top_n])

    def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        """Synchronous wrapper for arerank."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run, self.arerank(query=query, chunks=chunks, top_n=top_n)
                )
                return future.result()
        else:
            return asyncio.run(self.arerank(query=query, chunks=chunks, top_n=top_n))


class JinaReader:
    """Client for Jina Reader API (https://r.jina.ai/) for high-speed URL-to-markdown extraction.

    Converts web pages, circular portals, or PDFs into clean LLM-friendly Markdown.
    Supports usage with or without an API key.
    """

    READER_BASE_URL: str = "https://r.jina.ai/"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        settings = get_settings()
        self.api_key = settings.JINA_API_KEY if api_key is None else api_key
        self.timeout = timeout

    async def read_url(self, target_url: str) -> str:
        """Fetch and convert any web page or document URL to clean Markdown."""
        clean_url = target_url.strip()
        request_url = f"{self.READER_BASE_URL}{clean_url}"
        headers = {"Accept": "text/event-stream"}
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(request_url, headers=headers)
            resp.raise_for_status()
            return resp.text
