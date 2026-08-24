import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

from db.session import async_session_maker
from ingestion.pipeline import ingest_document
from models.document import Document

logger = logging.getLogger(__name__)


async def _run_reingest_all():
    logger.info("Starting scheduled re-ingestion of all documents")
    async with async_session_maker() as session:
        # Get all unique source URLs
        stmt = select(Document.source_url).distinct()
        result = await session.execute(stmt)
        urls = result.scalars().all()

        for url in urls:
            try:
                await ingest_document(session=session, source=url)
            except Exception as e:
                logger.error(f"Error re-ingesting {url}: {e}")


@shared_task(name="ingestion.tasks.reingest_all_documents")
def reingest_all_documents():
    """Celery task to re-ingest all registered documents."""
    asyncio.run(_run_reingest_all())


async def _run_reingest_single(source_url: str):
    logger.info(f"Starting manual re-ingestion for {source_url}")
    async with async_session_maker() as session:
        try:
            # We fetch existing metadata from DB
            stmt = select(Document).where(Document.source_url == source_url).limit(1)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()

            department = doc.department if doc else None
            owner = doc.owner if doc else None

            # Since source_type is an Enum/String in Document, we parse it if we can.
            # However, `SourceType` is an Enum in ingestion.schemas.
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
                force=True,  # Force re-embed on manual trigger
            )
        except Exception as e:
            logger.error(f"Error re-ingesting {source_url}: {e}")


@shared_task(name="ingestion.tasks.reingest_document")
def reingest_document(source_url: str):
    """Celery task to force re-ingest a single document."""
    asyncio.run(_run_reingest_single(source_url))
