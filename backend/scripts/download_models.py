"""Script to download and save embedding and reranker models locally in backend/models_cache/."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "models_cache"
EMBEDDING_DIR = CACHE_DIR / "all-MiniLM-L6-v2"
RERANKER_DIR = CACHE_DIR / "ms-marco-MiniLM-L-6-v2"


def download_models():
    os.makedirs(CACHE_DIR, exist_ok=True)
    print(f"Target Cache Directory: {CACHE_DIR}")

    # 1. Download Embedding Model (~85 MB)
    print("\n[1/2] Downloading & Saving Embedding Model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    embedder.save_pretrained(str(EMBEDDING_DIR))
    print(f"Successfully saved Embedding model to {EMBEDDING_DIR}")

    # 2. Download Reranker Model (~85 MB)
    print("\n[2/2] Downloading & Saving Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2)...")
    from sentence_transformers import CrossEncoder

    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    reranker.save_pretrained(str(RERANKER_DIR))
    print(f"Successfully saved Cross-Encoder model to {RERANKER_DIR}")

    print("\n All models downloaded and cached locally for 100% offline fast inference!")


if __name__ == "__main__":
    download_models()
