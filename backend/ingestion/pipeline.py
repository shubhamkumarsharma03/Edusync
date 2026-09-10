import logging
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.change_detector import ChangeDetector, ChangeStatus
from ingestion.chunker import chunk_document
from ingestion.conflict_detector import ConflictDetector
from ingestion.embedder import DocumentEmbedder
from ingestion.fetchers.factory import fetch_document
from ingestion.schemas import SourceType
from ingestion.upsert import upsert_document_and_chunks
from models.document import Document

logger = logging.getLogger(__name__)


class IngestionSummary(BaseModel):
    """Execution summary for a single document ingestion task."""

    source_url: str
    status: str
    reembedded: bool
    chunks_count: int = 0
    document_id: str | None = None
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceIngestionSummary(BaseModel):
    """Aggregated execution summary for a multi-document source ingestion task."""

    source_url: str
    total_checked: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    total_chunks: int = 0
    conflicted_count: int = 0
    message: str = ""
    details: list[IngestionSummary] = Field(default_factory=list)


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
    """High-level single-document ingestion pipeline.

    1. Fetches and parses document (PDF / HTML / Sheet).
    2. Runs content hash change detection vs PostgreSQL.
    3. If unchanged (and not force): returns immediately with 0 re-embed overhead.
    4. If new or modified: chunks text/tables and upserts embeddings into PostgreSQL.
    """
    logger.info(f"Starting ingestion for single document: {source}")

    try:
        # Pre-check existing document hash from DB for fast-path check
        if not force and "existing_hash" not in fetch_kwargs:
            stmt = select(Document.content_hash).where(Document.source_url == source)
            res = await session.execute(stmt)
            existing_h = res.scalar_one_or_none()
            if existing_h:
                fetch_kwargs["existing_hash"] = existing_h

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


async def ingest_source(
    session: AsyncSession,
    source_url: str,
    limit: int = 50,
    department: str | None = None,
    owner: str | None = None,
    force: bool = False,
    embedder: DocumentEmbedder | None = None,
) -> SourceIngestionSummary:
    """Ingest institutional sources like department circulars or timetables.

    Extracts up to `limit` individual notices and attached PDFs, running change-detection,
    semantic chunking, and embedding on each item.
    """
    logger.info(f"Starting source batch ingestion for {source_url} (limit={limit})")
    from ingestion.fetchers.ecajmer_fetcher import ECAjmerFetcher

    fetcher = ECAjmerFetcher()

    # Pre-query existing hashes for documents from DB to bypass OCR on unchanged PDFs
    existing_hashes: dict[str, str] = {}
    if not force:
        stmt = select(Document.source_url, Document.content_hash)
        if department:
            stmt = stmt.where(Document.department == department)
        rows = (await session.execute(stmt)).all()
        existing_hashes = {r[0]: r[1] for r in rows if r[0] and r[1]}

    docs = await fetcher.fetch_all_source_documents(
        source_url=source_url,
        limit=limit,
        department=department,
        existing_hashes=existing_hashes if not force else None,
    )

    if not docs:
        # Fallback to single document ingestion if not a multi-notice portal
        single_summary = await ingest_document(
            session=session,
            source=source_url,
            department=department,
            owner=owner,
            force=force,
            embedder=embedder,
        )
        return SourceIngestionSummary(
            source_url=source_url,
            total_checked=1,
            created_count=1 if single_summary.status == "created" else 0,
            updated_count=1 if single_summary.status == "updated" else 0,
            unchanged_count=1 if single_summary.status == "unchanged" else 0,
            total_chunks=single_summary.chunks_count,
            conflicted_count=1 if single_summary.status == "conflicted" else 0,
            message=single_summary.message,
            details=[single_summary],
        )

    summary = SourceIngestionSummary(
        source_url=source_url,
        total_checked=len(docs),
    )

    for fetched in docs:
        try:
            doc_dept = department or fetched.metadata.get("department")
            detection = await ChangeDetector.check_document(
                session, fetched, department=doc_dept, owner=owner
            )

            if detection.status == ChangeStatus.UNCHANGED and not force:
                summary.unchanged_count += 1
                summary.details.append(
                    IngestionSummary(
                        source_url=fetched.source_url,
                        status="unchanged",
                        reembedded=False,
                        chunks_count=0,
                        document_id=(
                            str(detection.existing_document_id)
                            if detection.existing_document_id
                            else None
                        ),
                        message="Content unchanged. Skipped re-embedding.",
                        metadata=fetched.metadata,
                    )
                )
                continue

            chunks = chunk_document(fetched, department=doc_dept, owner=owner)
            doc, chunk_records = await upsert_document_and_chunks(
                session=session,
                fetched=fetched,
                chunks=chunks,
                department=doc_dept,
                owner=owner,
                embedder=embedder,
            )

            is_conflicted = await ConflictDetector.check_conflicts(session, doc)
            action_status = "created" if detection.status == ChangeStatus.NEW else "updated"
            if is_conflicted:
                action_status = "conflicted"
                summary.conflicted_count += 1
            elif action_status == "created":
                summary.created_count += 1
            else:
                summary.updated_count += 1

            summary.total_chunks += len(chunk_records)
            summary.details.append(
                IngestionSummary(
                    source_url=fetched.source_url,
                    status=action_status,
                    reembedded=True,
                    chunks_count=len(chunk_records),
                    document_id=str(doc.id),
                    message=f"Successfully {action_status} notice ({len(chunk_records)} chunks).",
                    metadata=fetched.metadata,
                )
            )
        except Exception as e:
            logger.error(f"Error ingesting item {fetched.source_url}: {e}")

    summary.message = (
        f"Ingestion complete: {summary.total_checked} checked, "
        f"{summary.created_count} created, {summary.updated_count} updated, "
        f"{summary.unchanged_count} unchanged, {summary.total_chunks} total chunks."
    )
    return summary
