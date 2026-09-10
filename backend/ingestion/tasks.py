import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from db.session import async_session_maker
from ingestion.pipeline import ingest_document, ingest_source
from models.document import Document
from models.source import IngestionSource

logger = logging.getLogger(__name__)


async def _run_fetch_source(source_id: UUID | str, limit: int | None = None) -> dict:
    """Execute prioritized ingestion for a specific IngestionSource."""
    sid = UUID(str(source_id)) if isinstance(source_id, str) else source_id
    logger.info(f"Starting prioritized ingestion for source ID: {sid}")

    async with async_session_maker() as session:
        stmt = select(IngestionSource).where(IngestionSource.id == sid)
        result = await session.execute(stmt)
        source = result.scalar_one_or_none()

        if not source:
            logger.error(f"Source with ID {sid} not found")
            return {"error": "Source not found"}

        source.status = "fetching"
        source.error_message = None
        await session.commit()

        try:
            fetch_limit = limit
            if fetch_limit is None:
                fetch_limit = (
                    source.initial_fetch_limit
                    if source.last_fetched_at is None
                    else source.subsequent_fetch_limit
                )

            summary = await ingest_source(
                session=session,
                source_url=source.url,
                limit=fetch_limit,
                department=source.department,
            )

            source.status = "completed"
            source.last_fetched_at = datetime.now(UTC)
            source.error_message = None
            await session.commit()

            logger.info(f"Successfully finished ingestion for {source.name}: {summary.message}")
            return summary.model_dump()
        except Exception as e:
            logger.error(f"Error executing ingestion for source {source.url}: {e}", exc_info=True)
            source.status = "error"
            source.error_message = str(e)
            await session.commit()
            return {"error": str(e)}


@shared_task(name="ingestion.tasks.fetch_source_task")
def fetch_source_task(source_id: str):
    """Celery task to ingest a single configured source."""
    return asyncio.run(_run_fetch_source(source_id))


async def _run_fetch_all_sources_by_priority() -> list[dict]:
    """Execute ingestion for all active sources ordered strictly by priority ASC (1, 2, 3...)."""
    logger.info("Starting priority-queued batch ingestion across all active sources")
    results = []

    async with async_session_maker() as session:
        stmt = (
            select(IngestionSource)
            .where(IngestionSource.is_active == True)  # noqa: E712
            .order_by(IngestionSource.priority.asc(), IngestionSource.created_at.asc())
        )
        res = await session.execute(stmt)
        sources = res.scalars().all()
        source_ids = [s.id for s in sources]

    for sid in source_ids:
        try:
            res_summary = await _run_fetch_source(sid)
            results.append({"source_id": str(sid), "summary": res_summary})
        except Exception as err:
            logger.error(f"Failed during priority ingestion for {sid}: {err}")
            results.append({"source_id": str(sid), "error": str(err)})

    return results


@shared_task(name="ingestion.tasks.reingest_all_documents")
def reingest_all_documents():
    """Scheduled task to run prioritized ingestion across all configured sources."""
    asyncio.run(_run_fetch_all_sources_by_priority())


@shared_task(name="ingestion.tasks.fetch_all_sources_task")
def fetch_all_sources_task():
    """Celery task to run all sources in priority order."""
    return asyncio.run(_run_fetch_all_sources_by_priority())


async def _run_reingest_single(source_url: str):
    """Manual single-URL re-ingest fallback."""
    logger.info(f"Starting manual re-ingestion for {source_url}")
    async with async_session_maker() as session:
        try:
            stmt = select(Document).where(Document.source_url == source_url).limit(1)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            department = doc.department if doc else None
            owner = doc.owner if doc else None

            from ingestion.schemas import SourceType

            source_type_enum = None
            if doc and doc.source_type:
                try:
                    source_type_enum = SourceType(doc.source_type)
                except ValueError:
                    pass

            await ingest_document(
                session=session,
                source=source_url,
                source_type=source_type_enum,
                department=department,
                owner=owner,
                force=True,
            )
        except Exception as e:
            logger.error(f"Error re-ingesting {source_url}: {e}")


@shared_task(name="ingestion.tasks.reingest_document")
def reingest_document(source_url: str):
    """Celery task to force re-ingest a single document."""
    asyncio.run(_run_reingest_single(source_url))
