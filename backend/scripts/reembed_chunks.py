"""Utility script to compute and backfill vector embeddings for chunks in PostgreSQL.

Can be run anytime to embed chunks where embedding is None or to re-embed all chunks.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend directory to python path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select  # noqa: E402

from db.session import async_session_maker  # noqa: E402
from ingestion.embedder import DocumentEmbedder  # noqa: E402
from models.chunk import Chunk  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reembed_chunks")


async def reembed_chunks(only_missing: bool = True) -> int:
    """Compute and persist 1024-d embeddings for database chunks."""
    embedder = DocumentEmbedder()
    logger.info(
        f"Initialized DocumentEmbedder (Jina active: {embedder.jina_embedder is not None}, local: {embedder.model_name})"
    )

    async with async_session_maker() as session:
        stmt = select(Chunk).order_by(Chunk.id.asc())
        if only_missing:
            stmt = stmt.where(Chunk.embedding.is_(None))

        result = await session.execute(stmt)
        chunks = list(result.scalars().all())

        if not chunks:
            logger.info("No chunks require embedding.")
            return 0

        logger.info(f"Found {len(chunks)} chunks needing embeddings. Generating 1024-d vectors...")
        texts = [c.content for c in chunks]
        embeddings = await embedder.aembed_texts(texts, task="retrieval.passage", batch_size=32)

        for chunk, emb in zip(chunks, embeddings, strict=False):
            chunk.embedding = emb

        await session.commit()
        logger.info(f"Successfully updated and committed embeddings for {len(chunks)} chunks.")
        return len(chunks)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill or refresh embeddings for chunks in EduSync.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-embed all chunks in database (not just those with embedding is None)",
    )
    args = parser.parse_args()

    count = asyncio.run(reembed_chunks(only_missing=not args.all))
    print(f"Done. Processed {count} chunks.")
