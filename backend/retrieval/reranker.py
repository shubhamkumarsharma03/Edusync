import logging
import math
from collections.abc import Sequence
from typing import Any

from api.config import get_settings
from retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Hybrid Cross-Encoder reranker supporting Jina Reranker v2 API and local CPU CrossEncoder fallback."""

    _model: Any = None
    DEFAULT_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(
        self,
        model_name: str | None = None,
        model: Any = None,
        provider: str | None = None,
    ) -> None:
        settings = get_settings()
        self._model = model
        self.provider = provider or getattr(settings, "RERANKER_PROVIDER", "auto")
        self.model_name = model_name or getattr(
            settings, "RERANKER_MODEL_NAME", self.DEFAULT_MODEL_NAME
        )
        self.jina_reranker = None

        # Only use Jina API if an explicit model was not injected
        if self._model is None and self.provider in ("auto", "jina"):
            from retrieval.jina_client import JinaReranker

            candidate_jina = JinaReranker()
            if candidate_jina.is_available():
                self.jina_reranker = candidate_jina
                logger.info("CrossEncoderReranker initialized with Jina Reranker v2 API provider.")
            elif self.provider == "jina":
                logger.warning(
                    "Jina AI reranker provider requested but JINA_API_KEY is not configured. Falling back to local model."
                )

        if not self.jina_reranker:
            logger.info(f"CrossEncoderReranker using local model: {self.model_name}")

    def get_rerank_model(self) -> Any:
        """Return instance model if provided, otherwise retrieve singleton model."""
        if self._model is not None:
            return self._model
        return self.get_model(self.model_name)

    @classmethod
    def get_model(cls, model_name: str = DEFAULT_MODEL_NAME) -> Any:
        """Lazy load CrossEncoder model as a singleton on CPU from local cache or Hub."""
        if cls._model is None:
            from pathlib import Path

            from sentence_transformers import CrossEncoder

            # Check local models_cache folder
            base_model_name = model_name.split("/")[-1]
            local_cache_path = (
                Path(__file__).resolve().parent.parent / "models_cache" / base_model_name
            )
            target = str(local_cache_path) if local_cache_path.exists() else model_name

            logger.info(f"Loading CrossEncoder reranker model '{target}' on CPU...")
            cls._model = CrossEncoder(target, device="cpu")
        return cls._model

    @staticmethod
    def sigmoid(logit: float) -> float:
        """Compute sigmoid normalization mapping unbounded cross-encoder logits into [0, 1]."""
        # Clamp logit to prevent math overflow
        clamped = max(-50.0, min(50.0, float(logit)))
        return 1.0 / (1.0 + math.exp(-clamped))

    async def arerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Asynchronously rerank candidate chunks.

        Uses Jina Reranker v2 API when available, otherwise runs local CPU model in threadpool.
        """
        if not chunks or not query.strip():
            return list(chunks[:top_k])

        if self.jina_reranker:
            return await self.jina_reranker.arerank(query=query, chunks=chunks, top_n=top_k)

        import asyncio

        return await asyncio.to_thread(self.rerank, query=query, chunks=chunks, top_k=top_k)

    def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Rerank candidate chunks using Cross-Encoder semantic matching.

        Returns top_k chunks sorted by descending reranker score.
        """
        if not chunks or not query.strip():
            return list(chunks[:top_k])

        if self.jina_reranker:
            return self.jina_reranker.rerank(query=query, chunks=chunks, top_n=top_k)

        model = self.get_rerank_model()
        pairs = [(query, chunk.content) for chunk in chunks]

        raw_scores = model.predict(pairs, show_progress_bar=False)

        scored_chunks: list[tuple[float, RetrievedChunk]] = []
        for chunk, raw_score in zip(chunks, raw_scores, strict=False):
            norm_score = self.sigmoid(float(raw_score))
            chunk.rerank_score = norm_score
            chunk.score = norm_score
            scored_chunks.append((norm_score, chunk))

        # Sort descending by normalized rerank score
        scored_chunks.sort(key=lambda item: item[0], reverse=True)

        reranked_results: list[RetrievedChunk] = []
        for rank, (_, chunk) in enumerate(scored_chunks[:top_k], start=1):
            chunk.rank = rank
            reranked_results.append(chunk)

        logger.debug(
            f"Reranked {len(chunks)} candidate chunks to top {len(reranked_results)} items."
        )
        return reranked_results
