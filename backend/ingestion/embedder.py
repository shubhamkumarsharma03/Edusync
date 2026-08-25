import logging
from typing import Any

from ingestion.schemas import ChunkData

logger = logging.getLogger(__name__)


class DocumentEmbedder:
    """CPU-based sentence embedder using all-MiniLM-L6-v2 (384 dimensions)."""

    _model: Any = None
    MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or self.MODEL_NAME

    @classmethod
    def get_model(cls, model_name: str = MODEL_NAME) -> Any:
        """Lazy load SentenceTransformer model in singleton pattern from local cache or Hub."""
        if cls._model is None:
            import os
            from pathlib import Path
            from sentence_transformers import SentenceTransformer

            # Check local models_cache folder
            local_cache_path = Path(__file__).resolve().parent.parent / "models_cache" / model_name
            target = str(local_cache_path) if local_cache_path.exists() else model_name

            logger.info(f"Loading SentenceTransformer model '{target}' on CPU...")
            cls._model = SentenceTransformer(target, device="cpu")
        return cls._model


    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Compute 384-dimensional dense vector embeddings for a list of texts."""
        if not texts:
            return []

        model = self.get_model(self.model_name)
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [emb.tolist() for emb in embeddings]

    def embed_chunks(self, chunks: list[ChunkData], batch_size: int = 32) -> list[list[float]]:
        """Compute vector embeddings for a list of ChunkData instances."""
        texts = [chunk.content for chunk in chunks]
        return self.embed_texts(texts, batch_size=batch_size)
