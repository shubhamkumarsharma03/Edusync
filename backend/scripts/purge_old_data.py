"""Purge old document, chunk, conflict, and query data from PostgreSQL."""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402

from db.session import async_session_maker  # noqa: E402
from retrieval.jina_client import jina_token_tracker  # noqa: E402


async def purge_data():
    async with async_session_maker() as session:
        await session.execute(text("DELETE FROM chunks;"))
        await session.execute(text("DELETE FROM documents;"))
        await session.execute(text("DELETE FROM conflicts;"))
        await session.execute(text("DELETE FROM queries_log;"))
        await session.execute(
            text(
                "UPDATE ingestion_sources SET status = 'idle', last_fetched_at = NULL, error_message = NULL;"
            )
        )
        await session.commit()
        print(
            "Successfully purged chunks, documents, conflicts, queries_log, and reset ingestion_sources."
        )

    jina_token_tracker.reset()
    print("Reset Jina token tracker.")


if __name__ == "__main__":
    asyncio.run(purge_data())
