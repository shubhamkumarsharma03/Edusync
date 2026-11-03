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
from ingestion.notice_analyzer import NoticeAnalyzer
from ingestion.schemas import SourceType
from ingestion.supersession_resolver import SupersessionResolver
from ingestion.upsert import upsert_document_and_chunks
from models.department import Department
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
    department_id: int | None = None,
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
        # Resolve department_id from string department name if not provided
        if department_id is None and department is not None:
            dept_res = await session.execute(
                select(Department.id).where(
                    (Department.name.ilike(department)) | (Department.slug.ilike(department))
                )
            )
            department_id = dept_res.scalar_one_or_none()

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
            session, fetched, department_id=department_id, owner=owner
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

        # 4. Analyze notice metadata via single Gemini API call
        memory_data = await NoticeAnalyzer.analyze(fetched)

        # 5. Chunk document along semantic boundaries enriched with notice memory
        chunks = chunk_document(fetched, department=None, owner=owner, memory_data=memory_data)

        # 6. Embed and upsert into database + vector index
        doc, chunk_records = await upsert_document_and_chunks(
            session=session,
            fetched=fetched,
            chunks=chunks,
            department_id=department_id,
            owner=owner,
            embedder=embedder,
        )

        # 7. Resolve supersession and record notice memory
        await SupersessionResolver.resolve(session, memory_data, doc.id)

        # 8. Check for conflicts
        is_conflicted = await ConflictDetector.check_conflicts(session, doc)
        await session.commit()

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
        await session.rollback()
        logger.error(f"Ingestion failed for {source}: {e}", exc_info=True)
        raise


async def ingest_source(
    session: AsyncSession,
    source_url: str,
    limit: int = 50,
    department: str | None = None,
    department_id: int | None = None,
    owner: str | None = None,
    force: bool = False,
    embedder: DocumentEmbedder | None = None,
    source_id: str | None = None,
) -> SourceIngestionSummary:
    """Ingest institutional sources like department circulars or timetables.

    Extracts up to `limit` individual notices and attached PDFs, running change-detection,
    semantic chunking, and embedding on each item. Emits real-time progress updates.
    """
    logger.info(f"Starting source batch ingestion for {source_url} (limit={limit})")
    from ingestion.fetchers.ecajmer_fetcher import ECAjmerFetcher
    from ingestion.progress import progress_tracker

    department_name = None
    if department_id:
        stmt = select(Department).where(Department.id == department_id)
        dept = (await session.execute(stmt)).scalar_one_or_none()
        if dept:
            department_name = dept.name

    progress_tracker.update_step(
        phase="portal_fetch",
        step_index=1,
        current_action=f"Connecting to college portal API: {source_url.split('/')[-2] or 'circulars'}",
        next_action=f"Fetch up to {limit} recent notices and inspect attached PDF documents",
        source_id=source_id,
        log_message=f"Querying portal endpoints for department '{department_name or 'All'}' (limit={limit})",
        log_level="fetch",
        log_tag="PORTAL",
    )

    fetcher = ECAjmerFetcher()

    # Pre-query existing hashes for documents from DB to bypass OCR on unchanged PDFs
    existing_hashes: dict[str, str] = {}
    if not force:
        stmt = select(Document.source_url, Document.content_hash)
        if department_id:
            stmt = stmt.where(Document.department_id == department_id)
        rows = (await session.execute(stmt)).all()
        existing_hashes = {r[0]: r[1] for r in rows if r[0] and r[1]}

    docs = await fetcher.fetch_all_source_documents(
        source_url=source_url,
        limit=limit,
        department=department_name,
        existing_hashes=existing_hashes if not force else None,
        source_id=source_id,
    )

    if not docs:
        progress_tracker.log(
            "Portal returned 0 structured entries. Falling back to single-document fetch.",
            level="warn",
            source_id=source_id,
        )
        single_summary = await ingest_document(
            session=session,
            source=source_url,
            department_id=department_id,
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

    progress_tracker.update_step(
        phase="pdf_download",
        step_index=2,
        current_action=f"Discovered {len(docs)} notices from portal. Commencing content hashing & verification.",
        next_action="Perform SHA-256 hash comparison against existing PostgreSQL records",
        source_id=source_id,
        log_message=f"Found {len(docs)} notices to process from {source_url}",
        log_level="info",
        log_tag="INDEX",
        stats_update={"total": len(docs)},
    )

    summary = SourceIngestionSummary(
        source_url=source_url,
        total_checked=len(docs),
    )

    ocr_processed_count = 0

    for idx, fetched in enumerate(docs, start=1):
        fname = fetched.source_url.split("/")[-1] or f"document_{idx}.pdf"
        doc_title = fetched.metadata.get("title") or fname
        size_kb = round(len(fetched.raw_content) / 1024, 1) if fetched.raw_content else 0.0

        try:
            doc_dept_id = department_id

            # Step 2: Hash Check
            progress_tracker.update_step(
                phase="hash_check",
                step_index=2,
                current_action=f"[{idx}/{len(docs)}] Hashing {fname} ({size_kb} KB)",
                next_action="Compare content hash vs PostgreSQL to avoid re-embedding",
                source_id=source_id,
                active_document={
                    "title": doc_title,
                    "filename": fname,
                    "url": fetched.source_url,
                    "size_kb": size_kb,
                    "source_type": fetched.source_type,
                },
                log_message=f"[{idx}/{len(docs)}] Verifying SHA-256 hash for {fname}",
                log_level="fetch",
                log_tag="HASH",
                stats_update={"checked": idx},
            )

            detection = await ChangeDetector.check_document(
                session, fetched, department_id=doc_dept_id, owner=owner
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
                progress_tracker.update_step(
                    phase="hash_check",
                    step_index=2,
                    current_action=f"[{idx}/{len(docs)}] {fname} is UNCHANGED (0 re-embed cost)",
                    next_action=(
                        f"Next notice in queue ({idx+1}/{len(docs)})"
                        if idx < len(docs)
                        else "Finalize ingestion"
                    ),
                    source_id=source_id,
                    log_message=f"[{idx}/{len(docs)}] Content hash matched for {fname} -> Bypassing OCR & Re-embedding (Zero Cost)",
                    log_level="bypass",
                    log_tag="BYPASS",
                    stats_update={"bypassed_count": summary.unchanged_count},
                )
                continue

            # Step 3: OCR / Text extraction
            ocr_processed_count += 1
            progress_tracker.update_step(
                phase="ocr_inference",
                step_index=3,
                current_action=f"[{idx}/{len(docs)}] Layout parsing & OCR text extraction for {fname}",
                next_action="Perform semantic section chunking and Markdown table isolation",
                source_id=source_id,
                log_message=f"[{idx}/{len(docs)}] Parsing text layout and tables for {fname} ({size_kb} KB)",
                log_level="ocr",
                log_tag="OCR",
                stats_update={"ocr_count": ocr_processed_count},
            )

            # Step 3b: Analyze notice metadata via single Gemini API call
            memory_data = await NoticeAnalyzer.analyze(fetched)

            # Step 4: Semantic Chunking enriched with notice memory
            chunks = chunk_document(fetched, department=None, owner=owner, memory_data=memory_data)
            table_chunks_count = sum(1 for c in chunks if c.metadata.get("is_table"))

            progress_tracker.update_step(
                phase="chunking",
                step_index=4,
                current_action=f"[{idx}/{len(docs)}] Generated {len(chunks)} chunks ({table_chunks_count} isolated tables) for {fname}",
                next_action="Generate vector dense embeddings",
                source_id=source_id,
                log_message=f"[{idx}/{len(docs)}] Segmented into {len(chunks)} chunks ({table_chunks_count} tables isolated with row statements)",
                log_level="chunk",
                log_tag="CHUNK",
            )

            # Step 5: Embedding & Storage in pgvector
            progress_tracker.update_step(
                phase="embedding",
                step_index=5,
                current_action=f"[{idx}/{len(docs)}] Computing vector embeddings & upserting into pgvector",
                next_action=(
                    f"Proceed to next item ({idx+1}/{len(docs)})"
                    if idx < len(docs)
                    else "Finalize ingestion summary"
                ),
                source_id=source_id,
                log_message=f"[{idx}/{len(docs)}] Embedding {len(chunks)} chunks and storing in PostgreSQL",
                log_level="embed",
                log_tag="EMBED",
            )

            doc, chunk_records = await upsert_document_and_chunks(
                session=session,
                fetched=fetched,
                chunks=chunks,
                department_id=doc_dept_id,
                owner=owner,
                embedder=embedder,
            )

            # Step 5b: Resolve supersession and record notice memory
            await SupersessionResolver.resolve(session, memory_data, doc.id)

            is_conflicted = await ConflictDetector.check_conflicts(session, doc)
            await session.commit()

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
            progress_tracker.update_step(
                phase="embedding",
                step_index=5,
                current_action=f"[{idx}/{len(docs)}] Finished: {action_status} {fname}",
                next_action=(
                    f"Process next item ({idx+1}/{len(docs)})"
                    if idx < len(docs)
                    else "Finalize ingestion summary"
                ),
                source_id=source_id,
                log_message=f"[{idx}/{len(docs)}] Finished: {action_status} {fname} ({len(chunk_records)} vector chunks stored)",
                log_level="success",
                log_tag="STORED",
                stats_update={
                    "chunks_count": summary.total_chunks,
                    "created_count": summary.created_count,
                    "updated_count": summary.updated_count,
                    "checked": idx,
                },
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Error ingesting item {fetched.source_url}: {e}")
            progress_tracker.log(
                f"[{idx}/{len(docs)}] Error on {fname}: {e}",
                level="error",
                tag="ERROR",
                source_id=source_id,
            )

    summary.message = (
        f"Ingestion complete: {summary.total_checked} checked, "
        f"{summary.created_count} created, {summary.updated_count} updated, "
        f"{summary.unchanged_count} unchanged, {summary.total_chunks} total chunks."
    )
    return summary
