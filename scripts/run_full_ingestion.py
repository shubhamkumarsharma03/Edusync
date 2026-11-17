import asyncio
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from db.session import async_session_maker
from ingestion.tasks import _run_fetch_source
from models.chunk import Chunk
from models.document import Document
from models.source import IngestionSource
from sqlalchemy import func, select

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingestion_runner")


async def main():
    print("=" * 70)
    print("Starting EduSync Corpus Priority Ingestion (P1 through P28)")
    print("=" * 70)

    async with async_session_maker() as session:
        stmt = (
            select(IngestionSource)
            .where(IngestionSource.is_active == True)
            .order_by(IngestionSource.priority.asc(), IngestionSource.created_at.asc())
        )
        sources = (await session.execute(stmt)).scalars().all()
        source_tuples = [(s.id, s.priority, s.name, s.url, s.status) for s in sources]

    total_sources = len(source_tuples)
    print(f"Total active sources to process: {total_sources}\n")

    for idx, (sid, priority, name, url, status) in enumerate(source_tuples, 1):
        print(f"\n--- [{idx}/{total_sources}] P{priority}: {name} (status: {status}) ---")
        print(f"URL: {url}")
        try:
            res = await _run_fetch_source(sid)
            print(f"Result: {res.get('message', res)}")
        except Exception as e:
            print(f"Error ingesting source {name}: {e}")

    # Final Summary
    print("\n" + "=" * 70)
    print("Ingestion Run Completed! Generating Corpus Statistics...")
    print("=" * 70)

    async with async_session_maker() as session:
        doc_count = (await session.execute(select(func.count(Document.id)))).scalar()
        chunk_count = (await session.execute(select(func.count(Chunk.id)))).scalar()

        src_res = await session.execute(
            select(IngestionSource.status, func.count(IngestionSource.id)).group_by(
                IngestionSource.status
            )
        )
        status_counts = dict(src_res.all())

        print(f"Total Ingested Documents in DB : {doc_count}")
        print(f"Total Embedded Chunks in DB    : {chunk_count}")
        print(f"Source Status Breakdown        : {status_counts}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

