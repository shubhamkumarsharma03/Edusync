"""Script to download BAAI/bge-m3 locally and clean up obsolete local models."""

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "models_cache"
BGE_M3_DIR = CACHE_DIR / "bge-m3"
OLD_EMBEDDING_DIR = CACHE_DIR / "all-MiniLM-L6-v2"
HF_HUB_DIR = Path.home() / ".cache" / "huggingface" / "hub"
OLD_GOT_OCR_DIR = HF_HUB_DIR / "models--stepfun-ai--GOT-OCR-2.0-hf"


def clean_unused_models() -> None:
    print("\n--- Cleaning up obsolete local models ---")

    # 1. Remove old all-MiniLM-L6-v2
    if OLD_EMBEDDING_DIR.exists():
        print(f"Removing old embedding model: {OLD_EMBEDDING_DIR}...")
        shutil.rmtree(OLD_EMBEDDING_DIR, ignore_errors=True)
        print("Removed all-MiniLM-L6-v2 (~87 MB freed).")
    else:
        print("all-MiniLM-L6-v2 already cleaned.")

    # 2. Remove obsolete GOT-OCR from HF cache
    if OLD_GOT_OCR_DIR.exists():
        print(f"Removing obsolete local GOT-OCR cache: {OLD_GOT_OCR_DIR}...")
        shutil.rmtree(OLD_GOT_OCR_DIR, ignore_errors=True)
        print("Removed GOT-OCR-2.0-hf (~1.1 GB freed).")
    else:
        print("GOT-OCR-2.0-hf already cleaned.")


def download_bge_m3() -> None:
    print("\n--- Downloading BAAI/bge-m3 embedding model ---")
    print(f"Target Directory: {BGE_M3_DIR}")
    os.makedirs(CACHE_DIR, exist_ok=True)

    from sentence_transformers import SentenceTransformer

    print("Downloading & loading BAAI/bge-m3 (this may take a minute on initial download)...")
    model = SentenceTransformer("BAAI/bge-m3")

    print(f"Saving BGE-M3 weights locally to {BGE_M3_DIR}...")
    model.save_pretrained(str(BGE_M3_DIR))
    print(f"Successfully saved BAAI/bge-m3 to {BGE_M3_DIR}!")


if __name__ == "__main__":
    clean_unused_models()
    download_bge_m3()
    print("\nModel upgrade and cleanup complete!")
