import logging
from typing import Any

from api.config import get_settings
from ingestion.schemas import ChunkData

logger = logging.getLogger(__name__)


class DocumentEmbedder:
    """Hybrid document embedder supporting Jina Embeddings v3 API and local BAAI/bge-m3 fallback."""

    _model: Any = None
    MODEL_NAME: str = "bge-m3"
    EMBEDDING_DIM: int = 1024

    def __init__(
        self,
        model_name: str | None = None,
        provider: str | None = None,
    ) -> None:
        settings = get_settings()
        self.provider = provider or settings.EMBEDDING_PROVIDER
        self.model_name = model_name or self.MODEL_NAME
        self.jina_embedder = None

        if self.provider in ("auto", "jina"):
            from retrieval.jina_client import JinaEmbedder

            candidate_jina = JinaEmbedder()
            if candidate_jina.is_available():
                self.jina_embedder = candidate_jina
                logger.info("DocumentEmbedder initialized with Jina Embeddings v3 API provider.")
            elif self.provider == "jina":
                logger.warning(
                    "Jina AI provider requested but JINA_API_KEY is not configured. Falling back to local BGE-M3."
                )

        if not self.jina_embedder:
            logger.info(f"DocumentEmbedder using local model: {self.model_name}")

    @classmethod
    def get_model(cls, model_name: str = MODEL_NAME) -> Any:
        """Lazy load SentenceTransformer model in singleton pattern from local cache or Hub."""
        if cls._model is None:
            from pathlib import Path

            from sentence_transformers import SentenceTransformer

            # Check local models_cache folder
            base_cache_path = Path(__file__).resolve().parent.parent / "models_cache"
            short_name = model_name.split("/")[-1]
            local_cache_path = base_cache_path / short_name
            if not local_cache_path.exists():
                local_cache_path = base_cache_path / model_name

            target = str(local_cache_path) if local_cache_path.exists() else model_name

            logger.info(f"Loading SentenceTransformer model '{target}' on CPU...")
            cls._model = SentenceTransformer(target, device="cpu")
            if hasattr(cls._model, "max_seq_length"):
                cls._model.max_seq_length = min(getattr(cls._model, "max_seq_length", 8192), 8192)
        return cls._model

    async def aembed_texts(
        self,
        texts: list[str],
        task: str = "retrieval.passage",
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Asynchronously compute 1024-dimensional embeddings for texts."""
        if not texts:
            return []

        if self.jina_embedder:
            return await self.jina_embedder.aembed_texts(texts, task=task)

        # Fall back to threadpool execution for CPU SentenceTransformer
        import asyncio

        return await asyncio.to_thread(self.embed_texts, texts, batch_size=batch_size)

    async def aembed_chunks(
        self,
        chunks: list[ChunkData],
        task: str = "retrieval.passage",
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Asynchronously compute vector embeddings for a list of ChunkData instances."""
        texts = [chunk.content for chunk in chunks]
        return await self.aembed_texts(texts, task=task, batch_size=batch_size)

    def embed_texts(
        self,
        texts: list[str],
        batch_size: int = 32,
        task: str = "retrieval.passage",
    ) -> list[list[float]]:
        """Compute 1024-dimensional dense vector embeddings for a list of texts."""
        if not texts:
            return []

        if self.jina_embedder:
            return self.jina_embedder.embed_texts(texts, task=task)

        model = self.get_model(self.model_name)
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [emb.tolist() for emb in embeddings]

    def embed_chunks(
        self,
        chunks: list[ChunkData],
        batch_size: int = 32,
        task: str = "retrieval.passage",
    ) -> list[list[float]]:
        """Compute vector embeddings for a list of ChunkData instances."""
        texts = [chunk.content for chunk in chunks]
        return self.embed_texts(texts, batch_size=batch_size, task=task)
