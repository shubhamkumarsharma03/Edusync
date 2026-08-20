import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.change_detector import ChangeDetector, ChangeStatus
from ingestion.chunker import chunk_document
from ingestion.embedder import DocumentEmbedder
from ingestion.fetchers.factory import fetch_document
from ingestion.schemas import SourceType
from ingestion.upsert import upsert_document_and_chunks
from ingestion.conflict_detector import ConflictDetector

logger = logging.getLogger(__name__)


class IngestionSummary(BaseModel):
    """Execution summary for a document ingestion task."""

    source_url: str
    status: str
    reembedded: bool
    chunks_count: int = 0
    document_id: str | None = None
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


async def ingest_document(
    session: AsyncSession,
    source: str,
    source_type: SourceType | None = None,
    department: str | None = None,
    owner: str | None = None,
    force: bool = False,
    embedder: DocumentEmbedder | None = None,
    **fetch_kwargs: Any,
) -> IngestionSummary:
    """High-level end-to-end ingestion pipeline.

    1. Fetches and parses document (PDF / HTML / Sheet).
    2. Runs content hash change detection vs PostgreSQL.
    3. If unchanged (and not force): returns immediately with 0 re-embed overhead.
    4. If new or modified: chunks text/tables and upserts embeddings into PostgreSQL.
    """
    logger.info(f"Starting ingestion for: {source}")

    try:
        # 1. Fetch document content
        fetched = await fetch_document(source, source_type=source_type, **fetch_kwargs)

        # 2. Check for changes against stored content hash
        detection = await ChangeDetector.check_document(
            session, fetched, department=department, owner=owner
        )

        # 3. Handle unchanged document (Zero re-embedding invariant)
        if detection.status == ChangeStatus.UNCHANGED and not force:
            logger.info(f"Document unchanged: {source} (0 re-embed cost)")
            return IngestionSummary(
                source_url=source,
                status="unchanged",
                reembedded=False,
                chunks_count=0,
                document_id=(
                    str(detection.existing_document_id) if detection.existing_document_id else None
                ),
                message="Document content is unchanged. Skipped re-embedding.",
            )

        # 4. Chunk document along semantic boundaries
        chunks = chunk_document(fetched, department=department, owner=owner)

        # 5. Embed and upsert into database + vector index
        doc, chunk_records = await upsert_document_and_chunks(
            session=session,
            fetched=fetched,
            chunks=chunks,
            department=department,
            owner=owner,
            embedder=embedder,
        )

        # 6. Check for conflicts
        is_conflicted = await ConflictDetector.check_conflicts(session, doc)

        action_status = "created" if detection.status == ChangeStatus.NEW else "updated"
        if is_conflicted:
            action_status = "conflicted"
            
        return IngestionSummary(
            source_url=source,
            status=action_status,
            reembedded=True,
            chunks_count=len(chunk_records),
            document_id=str(doc.id),
            message=f"Successfully {action_status} document with {len(chunk_records)} vector chunks.",
            metadata={"source_type": fetched.source_type, "tables_count": len(fetched.tables)},
        )
    except Exception as e:
        logger.error(f"Ingestion failed for {source}: {e}", exc_info=True)
        raise
