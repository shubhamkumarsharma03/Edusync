import logging
import math
from collections.abc import Sequence
from typing import Any

from api.config import get_settings
from retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """CPU-based Cross-Encoder reranker to rescore and order candidate chunks."""

    _model: Any = None
    DEFAULT_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str | None = None, model: Any = None) -> None:
        settings = get_settings()
        self.model_name = model_name or getattr(
            settings, "RERANKER_MODEL_NAME", self.DEFAULT_MODEL_NAME
        )
        self._model = model

    def get_rerank_model(self) -> Any:
        """Return instance model if provided, otherwise retrieve singleton model."""
        if self._model is not None:
            return self._model
        return self.get_model(self.model_name)

    @classmethod
    def get_model(cls, model_name: str = DEFAULT_MODEL_NAME) -> Any:
        """Lazy load CrossEncoder model as a singleton on CPU."""
        if cls._model is None:
            logger.info(f"Loading CrossEncoder reranker model '{model_name}' on CPU...")
            from sentence_transformers import CrossEncoder

            cls._model = CrossEncoder(model_name, device="cpu")
        return cls._model

    @staticmethod
    def sigmoid(logit: float) -> float:
        """Compute sigmoid normalization mapping unbounded cross-encoder logits into [0, 1]."""
        # Clamp logit to prevent math overflow
        clamped = max(-50.0, min(50.0, float(logit)))
        return 1.0 / (1.0 + math.exp(-clamped))

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
