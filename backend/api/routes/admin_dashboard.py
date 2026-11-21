import csv
import io
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.config import get_settings
from db.session import get_db
from models.chunk import Chunk
from models.conflict import Conflict
from models.document import Document
from models.query_log import QueryLog
from models.source import IngestionSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])
settings = get_settings()


# --- Auth Schemas ---
class AdminAuthRequest(BaseModel):
    password: str = Field(..., description="Admin shared passcode")


class AdminAuthResponse(BaseModel):
    authenticated: bool
    message: str


# --- Document Schemas ---
class AdminDocumentItem(BaseModel):
    id: UUID
    source_url: str
    source_type: str
    department_id: int | None = None
    department_name: str | None = None
    title: str
    notice_sno: str | None = None
    notice_date: str | None = None
    status: str
    content_hash: str
    chunk_count: int
    ingested_at: datetime
    last_checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminDocumentsListResponse(BaseModel):
    total: int
    page: int
    limit: int
    documents: list[AdminDocumentItem]


class DocumentStatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        description="Target status: fresh, stale, conflicted, pending, or archived",
    )


class DocumentBulkActionRequest(BaseModel):
    document_ids: list[UUID]
    action: str = Field(
        ...,
        description="Bulk action: 'reingest', 'update_status', or 'delete'",
    )
    target_status: str | None = Field(
        None,
        description="Required if action is 'update_status'",
    )


class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    notice_sno: str | None = None
    notice_date: str | None = None
    department_id: int | None = None
    status: str | None = None


class ManualNoticeUploadRequest(BaseModel):
    title: str = Field(..., description="Notice title")
    notice_sno: str | None = None
    notice_date: str | None = None
    department_id: int | None = None
    content: str = Field(..., description="Raw text / Markdown content of circular")
    source_url: str | None = None


class DocumentChunkItem(BaseModel):
    id: UUID
    document_id: UUID
    content: str
    original_content: str | None = None
    token_count: int
    last_verified: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Conflict Schemas ---
class ConflictDocumentDetail(BaseModel):
    id: UUID
    title: str
    notice_sno: str | None = None
    notice_date: str | None = None
    status: str
    source_url: str
    department_name: str | None = None


class ConflictItemResponse(BaseModel):
    id: UUID
    document_ids: list[UUID]
    detected_at: datetime
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    documents: list[ConflictDocumentDetail]

    model_config = ConfigDict(from_attributes=True)


class ConflictResolveRequest(BaseModel):
    authoritative_document_id: UUID | None = None
    resolution_type: str = Field(
        "supersede",
        description="Resolution strategy: 'supersede', 'non_conflicting', 'archive_both', 'drop_both', or 'dismiss'",
    )
    notes: str | None = None


class ConflictCompareDocument(BaseModel):
    id: UUID
    title: str
    notice_sno: str | None = None
    notice_date: str | None = None
    status: str
    source_url: str
    department_name: str | None = None
    chunks: list[DocumentChunkItem]


class ConflictCompareResponse(BaseModel):
    conflict_id: UUID
    detected_at: datetime
    resolution_note: str | None = None
    documents: list[ConflictCompareDocument]


# --- Analytics Schemas ---
class RecentQueryItem(BaseModel):
    id: UUID
    question: str
    answer_preview: str | None = None
    confidence_score: float | None = None
    feedback: str | None = None
    created_at: datetime


class ConfidenceTierBreakdown(BaseModel):
    high_count: int
    medium_count: int
    low_count: int
    high_percentage: float
    medium_percentage: float
    low_percentage: float


class AnalyticsResponse(BaseModel):
    total_queries: int
    total_documents: int
    total_chunks: int
    total_sources: int
    unresolved_conflicts: int
    feedback_stats: dict[str, int | float]
    fallback_rate: float
    recent_queries: list[RecentQueryItem]
    top_fallback_questions: list[str]
    confidence_distribution: ConfidenceTierBreakdown | None = None


# --- System Tools Schemas ---
class DiagnosticChunkItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    department: str | None = None
    source_url: str
    content_snippet: str
    vector_score: float | None = None
    keyword_score: float | None = None
    rrf_score: float
    rerank_score: float | None = None
    rank: int


class RAGPlaygroundRequest(BaseModel):
    query: str
    department: str | None = None
    top_k: int = 5


class RAGPlaygroundResponse(BaseModel):
    query: str
    execution_time_ms: float
    passed_gate: bool
    confidence_level: str
    confidence_score: float
    is_fallback: bool
    fallback_message: str | None = None
    chunks: list[DiagnosticChunkItem]


class SystemHealthResponse(BaseModel):
    status: str
    db_ping_ms: float
    total_documents: int
    total_chunks: int
    total_sources: int
    unresolved_conflicts: int
    pgvector_installed: bool


# ---------------------------------------------------------------------------
# 1. Admin Authentication Gate
# ---------------------------------------------------------------------------
@router.post("/auth/verify", response_model=AdminAuthResponse)
async def verify_admin_auth(payload: AdminAuthRequest) -> AdminAuthResponse:
    """Verify shared admin passcode for basic dashboard gate."""
    expected_secret = getattr(settings, "ADMIN_SECRET_KEY", "edusync-admin-2026")
    if payload.password.strip() == expected_secret:
        return AdminAuthResponse(authenticated=True, message="Admin authentication successful")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin passcode")


# ---------------------------------------------------------------------------
# 2. Documents Management Table (All Ingested Documents)
# ---------------------------------------------------------------------------
@router.get("/documents", response_model=AdminDocumentsListResponse)
async def list_admin_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    department_id: int | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> AdminDocumentsListResponse:
    """List all ingested documents with status badges, chunk counts, and filters."""
    query = select(Document).options(selectinload(Document.department_rel))

    if status_filter and status_filter.lower() != "all":
        query = query.where(Document.status == status_filter.lower())

    if department_id is not None:
        query = query.where(Document.department_id == department_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Document.title.ilike(term),
                Document.notice_sno.ilike(term),
                Document.source_url.ilike(term),
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Sort in exact chronological portal order
    query = query.order_by(
        Document.notice_date.desc().nullslast(),
        Document.notice_sno.desc().nullslast(),
        Document.ingested_at.desc(),
    )

    # Paginate
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    docs = (await session.execute(query)).scalars().all()

    # Pre-fetch chunk counts for this page of documents
    doc_ids = [d.id for d in docs]
    chunk_counts: dict[UUID, int] = {}
    if doc_ids:
        chunk_count_stmt = (
            select(Chunk.document_id, func.count(Chunk.id))
            .where(Chunk.document_id.in_(doc_ids))
            .group_by(Chunk.document_id)
        )
        counts = (await session.execute(chunk_count_stmt)).all()
        chunk_counts = dict(counts)

    items: list[AdminDocumentItem] = []
    for d in docs:
        dept_name = d.department_rel.name if d.department_rel else None
        items.append(
            AdminDocumentItem(
                id=d.id,
                source_url=d.source_url,
                source_type=d.source_type,
                department_id=d.department_id,
                department_name=dept_name,
                title=d.title or "Untitled Notice",
                notice_sno=d.notice_sno,
                notice_date=str(d.notice_date) if d.notice_date else None,
                status=d.status,
                content_hash=d.content_hash,
                chunk_count=chunk_counts.get(d.id, 0),
                ingested_at=d.ingested_at,
                last_checked_at=d.last_checked_at,
            )
        )

    return AdminDocumentsListResponse(
        total=total,
        page=page,
        limit=limit,
        documents=items,
    )


@router.post("/documents/{document_id}/reingest")
async def reingest_single_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Manually re-ingest a document with force=True, updating status to fresh."""
    stmt = (
        select(Document)
        .options(selectinload(Document.department_rel))
        .where(Document.id == document_id)
    )
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from ingestion.pipeline import ingest_document

    dept_name = doc.department_rel.name if doc.department_rel else None
    summary = await ingest_document(
        session=session,
        source=doc.source_url,
        source_type=doc.source_type,
        department=dept_name,
        department_id=doc.department_id,
        force=True,
    )

    return {
        "status": "success",
        "document_id": str(document_id),
        "chunks_count": summary.chunks_count,
        "message": f"Successfully re-ingested document with {summary.chunks_count} chunks.",
    }


@router.patch("/documents/{document_id}/status")
async def update_document_status(
    document_id: UUID,
    payload: DocumentStatusUpdateRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Manually override a document's status (fresh, stale, conflicted, pending, archived)."""
    valid_statuses = {"fresh", "stale", "conflicted", "pending", "archived"}
    tgt = payload.status.lower()
    if tgt not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    stmt = select(Document).where(Document.id == document_id)
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = tgt
    await session.commit()
    logger.info(f"Document {document_id} status manually updated to {tgt}")
    return {"status": "success", "document_id": str(document_id), "new_status": tgt}


@router.put("/documents/{document_id}")
async def update_document_metadata(
    document_id: UUID,
    payload: DocumentUpdateRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update metadata (title, S.No, notice date, department) of an existing notice."""
    from datetime import date

    stmt = select(Document).where(Document.id == document_id)
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.title is not None:
        doc.title = payload.title.strip()
    if payload.notice_sno is not None:
        doc.notice_sno = payload.notice_sno.strip() if payload.notice_sno else None
    if payload.department_id is not None:
        doc.department_id = payload.department_id
    if payload.notice_date is not None:
        try:
            doc.notice_date = (
                date.fromisoformat(payload.notice_date) if payload.notice_date else None
            )
        except Exception:
            pass
    if payload.status is not None:
        valid_statuses = {"fresh", "stale", "conflicted", "pending", "archived"}
        if payload.status.lower() in valid_statuses:
            doc.status = payload.status.lower()

    await session.commit()
    return {
        "status": "success",
        "document_id": str(document_id),
        "message": "Document metadata updated successfully.",
    }


@router.post("/documents/manual-upload")
async def manual_upload_document(
    payload: ManualNoticeUploadRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Manually ingest an offline notice or emergency circular with text and metadata."""
    import hashlib
    from datetime import date

    from ingestion.chunker import DocumentChunker
    from ingestion.embedder import DocumentEmbedder

    content_hash = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()
    parsed_date = None
    if payload.notice_date:
        try:
            parsed_date = date.fromisoformat(payload.notice_date)
        except Exception:
            parsed_date = None

    source_url = (
        payload.source_url
        or f"https://ecajmer.ac.in/manual/{payload.notice_sno or content_hash[:8]}"
    )

    doc = Document(
        source_url=source_url,
        source_type="html",
        department_id=payload.department_id,
        title=payload.title,
        notice_sno=payload.notice_sno,
        notice_date=parsed_date,
        content_hash=content_hash,
        status="fresh",
    )
    session.add(doc)
    await session.flush()

    chunker = DocumentChunker()
    chunks_text = chunker.chunk_document(payload.content)
    if not chunks_text:
        chunks_text = [payload.content]

    embedder = DocumentEmbedder()
    embeddings = embedder.embed_chunks(chunks_text)

    for ct, emb in zip(chunks_text, embeddings, strict=False):
        ch = Chunk(
            document_id=doc.id,
            content=ct,
            original_content=ct,
            token_count=len(ct.split()),
            embedding=emb,
        )
        session.add(ch)

    await session.commit()
    logger.info(
        f"Manual document '{doc.title}' ingested with {len(chunks_text)} chunks (ID: {doc.id})"
    )
    return {
        "status": "success",
        "document_id": str(doc.id),
        "title": doc.title,
        "chunks_count": len(chunks_text),
        "message": f"Successfully ingested manual notice with {len(chunks_text)} chunks.",
    }


@router.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkItem])
async def get_document_chunks_list(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DocumentChunkItem]:
    """Retrieve all chunks belonging to a document for inspection."""
    stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.id)
    chunks = (await session.execute(stmt)).scalars().all()
    return [
        DocumentChunkItem(
            id=c.id,
            document_id=c.document_id,
            content=c.content,
            original_content=c.original_content,
            token_count=c.token_count,
            last_verified=c.last_verified,
        )
        for c in chunks
    ]


@router.delete("/documents/{document_id}")
async def delete_single_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Purge a single document and cascade delete its chunks."""
    stmt = select(Document).where(Document.id == document_id)
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clean up any conflict referencing this document
    conflicts_stmt = select(Conflict).where(Conflict.document_ids.contains([document_id]))
    conflicts = (await session.execute(conflicts_stmt)).scalars().all()
    for c in conflicts:
        new_ids = [did for did in c.document_ids if did != document_id]
        if len(new_ids) <= 1:
            c.resolved_at = datetime.now(UTC)
            c.resolved_by = "system"
            c.resolution_note = "Auto-resolved because conflicting document was deleted."
        c.document_ids = new_ids

    await session.delete(doc)
    await session.commit()
    logger.info(f"Document {document_id} deleted by admin.")
    return {"status": "success", "document_id": str(document_id), "message": "Document deleted."}


@router.post("/documents/bulk-action")
async def bulk_action_documents(
    payload: DocumentBulkActionRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Perform bulk actions across multiple documents (reingest, update_status, delete)."""
    action = payload.action.lower()
    doc_ids = payload.document_ids
    if not doc_ids:
        return {"status": "success", "affected_count": 0}

    if action == "reingest":
        from ingestion.pipeline import ingest_document

        stmt = (
            select(Document)
            .options(selectinload(Document.department_rel))
            .where(Document.id.in_(doc_ids))
        )
        docs = (await session.execute(stmt)).scalars().all()
        count = 0
        for d in docs:
            dept_name = d.department_rel.name if d.department_rel else None
            try:
                await ingest_document(
                    session=session,
                    source=d.source_url,
                    source_type=d.source_type,
                    department=dept_name,
                    department_id=d.department_id,
                    force=True,
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to bulk reingest {d.id}: {e}")
        return {"status": "success", "action": "reingest", "affected_count": count}

    elif action == "update_status":
        if not payload.target_status:
            raise HTTPException(
                status_code=400, detail="target_status is required for update_status action"
            )
        valid_statuses = {"fresh", "stale", "conflicted", "pending", "archived"}
        tgt = payload.target_status.lower()
        if tgt not in valid_statuses:
            raise HTTPException(
                status_code=400, detail=f"Invalid target_status '{payload.target_status}'"
            )
        stmt = select(Document).where(Document.id.in_(doc_ids))
        docs = (await session.execute(stmt)).scalars().all()
        for d in docs:
            d.status = tgt
        await session.commit()
        return {
            "status": "success",
            "action": "update_status",
            "affected_count": len(docs),
            "new_status": tgt,
        }

    elif action == "delete":
        stmt = select(Document).where(Document.id.in_(doc_ids))
        docs = (await session.execute(stmt)).scalars().all()
        count = len(docs)
        for d in docs:
            await session.delete(d)
        await session.commit()
        return {"status": "success", "action": "delete", "affected_count": count}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown bulk action '{payload.action}'")


# ---------------------------------------------------------------------------
# 3. Conflicts Management Panel
# ---------------------------------------------------------------------------
@router.get("/conflicts", response_model=list[ConflictItemResponse])
async def list_conflicts(
    unresolved_only: bool = Query(False),
    session: AsyncSession = Depends(get_db),
) -> list[ConflictItemResponse]:
    """Retrieve all detected conflicts with their linked documents."""
    query = select(Conflict).order_by(Conflict.detected_at.desc())
    if unresolved_only:
        query = query.where(Conflict.resolved_at.is_(None))

    conflicts = (await session.execute(query)).scalars().all()

    # Collect all doc IDs
    all_doc_ids = []
    for c in conflicts:
        all_doc_ids.extend(c.document_ids)

    doc_map: dict[UUID, Document] = {}
    if all_doc_ids:
        docs_stmt = (
            select(Document)
            .options(selectinload(Document.department_rel))
            .where(Document.id.in_(all_doc_ids))
        )
        docs = (await session.execute(docs_stmt)).scalars().all()
        doc_map = {d.id: d for d in docs}

    results: list[ConflictItemResponse] = []
    for c in conflicts:
        doc_details: list[ConflictDocumentDetail] = []
        for did in c.document_ids:
            d = doc_map.get(did)
            if d:
                doc_details.append(
                    ConflictDocumentDetail(
                        id=d.id,
                        title=d.title or "Untitled Notice",
                        notice_sno=d.notice_sno,
                        notice_date=str(d.notice_date) if d.notice_date else None,
                        status=d.status,
                        source_url=d.source_url,
                        department_name=d.department_rel.name if d.department_rel else None,
                    )
                )

        results.append(
            ConflictItemResponse(
                id=c.id,
                document_ids=c.document_ids,
                detected_at=c.detected_at,
                resolved_by=c.resolved_by,
                resolved_at=c.resolved_at,
                resolution_note=c.resolution_note,
                documents=doc_details,
            )
        )

    return results


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict_item(
    conflict_id: UUID,
    payload: ConflictResolveRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Resolve a conflict: mark authoritative, mark non-conflicting, drop/archive both, or dismiss."""
    stmt = select(Conflict).where(Conflict.id == conflict_id)
    conflict = (await session.execute(stmt)).scalar_one_or_none()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict record not found")

    docs_stmt = select(Document).where(Document.id.in_(conflict.document_ids))
    docs = (await session.execute(docs_stmt)).scalars().all()

    now = datetime.now(UTC)
    res_type = payload.resolution_type.lower()
    note = payload.notes or "Admin verified conflict resolution."

    if res_type == "supersede" and payload.authoritative_document_id:
        # Mark authoritative as fresh, others as archived
        for d in docs:
            if d.id == payload.authoritative_document_id:
                d.status = "fresh"
            else:
                d.status = "archived"
        conflict.resolution_note = (
            f"Authoritative document selected ({payload.authoritative_document_id}). {note}"
        )
    elif res_type in ("archive_both", "drop_both"):
        # Both/all documents are invalid/superseded by external factors -> archive all
        for d in docs:
            d.status = "archived"
        conflict.resolution_note = f"All conflicting documents dropped & archived by admin. {note}"
    elif res_type == "non_conflicting":
        # Both/all documents are valid (e.g. Sem 3 vs Sem 7 fee order)
        for d in docs:
            d.status = "fresh"
        conflict.resolution_note = f"Verified non-conflicting by admin. {note}"
    else:
        # Dismiss conflict, restore statuses to fresh
        for d in docs:
            if d.status == "conflicted":
                d.status = "fresh"
        conflict.resolution_note = f"Conflict dismissed by admin. {note}"

    conflict.resolved_by = "admin"
    conflict.resolved_at = now

    await session.commit()
    logger.info(f"Conflict {conflict_id} resolved as {res_type} by admin.")
    return {
        "status": "success",
        "conflict_id": str(conflict_id),
        "resolution_type": res_type,
        "resolution_note": conflict.resolution_note,
    }


@router.post("/conflicts/{conflict_id}/reopen")
async def reopen_conflict_item(
    conflict_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reopen a previously resolved conflict and return documents to conflicted status."""
    stmt = select(Conflict).where(Conflict.id == conflict_id)
    conflict = (await session.execute(stmt)).scalar_one_or_none()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict record not found")

    docs_stmt = select(Document).where(Document.id.in_(conflict.document_ids))
    docs = (await session.execute(docs_stmt)).scalars().all()
    for d in docs:
        d.status = "conflicted"

    conflict.resolved_at = None
    conflict.resolved_by = None
    conflict.resolution_note = "Reopened by admin for re-examination."

    await session.commit()
    logger.info(f"Conflict {conflict_id} reopened by admin.")
    return {"status": "success", "conflict_id": str(conflict_id), "message": "Conflict reopened."}


@router.get("/conflicts/{conflict_id}/compare", response_model=ConflictCompareResponse)
async def compare_conflict_documents(
    conflict_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> ConflictCompareResponse:
    """Retrieve full text and chunks of documents in conflict for side-by-side visual diff."""
    stmt = select(Conflict).where(Conflict.id == conflict_id)
    conflict = (await session.execute(stmt)).scalar_one_or_none()
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict record not found")

    docs_stmt = (
        select(Document)
        .options(selectinload(Document.department_rel))
        .where(Document.id.in_(conflict.document_ids))
    )
    docs = (await session.execute(docs_stmt)).scalars().all()

    doc_list: list[ConflictCompareDocument] = []
    for d in docs:
        chunks_stmt = select(Chunk).where(Chunk.document_id == d.id).order_by(Chunk.id)
        chunks = (await session.execute(chunks_stmt)).scalars().all()
        chunk_items = [
            DocumentChunkItem(
                id=c.id,
                document_id=c.document_id,
                content=c.content,
                original_content=c.original_content,
                token_count=c.token_count,
                last_verified=c.last_verified,
            )
            for c in chunks
        ]
        doc_list.append(
            ConflictCompareDocument(
                id=d.id,
                title=d.title or "Untitled Notice",
                notice_sno=d.notice_sno,
                notice_date=str(d.notice_date) if d.notice_date else None,
                status=d.status,
                source_url=d.source_url,
                department_name=d.department_rel.name if d.department_rel else None,
                chunks=chunk_items,
            )
        )

    return ConflictCompareResponse(
        conflict_id=conflict.id,
        detected_at=conflict.detected_at,
        resolution_note=conflict.resolution_note,
        documents=doc_list,
    )


# ---------------------------------------------------------------------------
# 4. Analytics & Health Panel
# ---------------------------------------------------------------------------
@router.get("/analytics", response_model=AnalyticsResponse)
async def get_admin_analytics(
    query_filter: str = Query(
        "all", description="Filter recent queries: all, positive, negative, unrated, fallback"
    ),
    session: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    """Retrieve operational metrics, query volume, feedback breakdown, and fallbacks."""
    # 1. Total counts
    total_docs = (await session.execute(select(func.count(Document.id)))).scalar() or 0
    total_chunks = (await session.execute(select(func.count(Chunk.id)))).scalar() or 0
    total_sources = (await session.execute(select(func.count(IngestionSource.id)))).scalar() or 0
    unresolved_conflicts = (
        await session.execute(select(func.count(Conflict.id)).where(Conflict.resolved_at.is_(None)))
    ).scalar() or 0

    # 2. Query statistics
    total_queries = (await session.execute(select(func.count(QueryLog.id)))).scalar() or 0

    up_count = (
        await session.execute(select(func.count(QueryLog.id)).where(QueryLog.feedback == "up"))
    ).scalar() or 0

    down_count = (
        await session.execute(select(func.count(QueryLog.id)).where(QueryLog.feedback == "down"))
    ).scalar() or 0

    unrated_count = total_queries - (up_count + down_count)
    positive_rate = (
        (up_count / (up_count + down_count)) * 100 if (up_count + down_count) > 0 else 100.0
    )

    # 3. Fallbacks (confidence <= 0.40)
    fallback_count = (
        await session.execute(
            select(func.count(QueryLog.id)).where(
                or_(QueryLog.confidence_score.is_(None), QueryLog.confidence_score <= 0.40)
            )
        )
    ).scalar() or 0
    fallback_rate = (fallback_count / total_queries) * 100 if total_queries > 0 else 0.0

    # 4. Top Fallback Questions
    fallback_stmt = (
        select(QueryLog.question)
        .where(or_(QueryLog.confidence_score.is_(None), QueryLog.confidence_score <= 0.40))
        .order_by(QueryLog.created_at.desc())
        .limit(5)
    )
    fallback_questions = (await session.execute(fallback_stmt)).scalars().all()

    # 5. Recent Queries (with filter support)
    recent_query = select(QueryLog).order_by(QueryLog.created_at.desc())
    f = query_filter.lower()
    if f == "positive":
        recent_query = recent_query.where(QueryLog.feedback == "up")
    elif f == "negative":
        recent_query = recent_query.where(QueryLog.feedback == "down")
    elif f == "unrated":
        recent_query = recent_query.where(QueryLog.feedback.is_(None))
    elif f == "fallback":
        recent_query = recent_query.where(
            or_(QueryLog.confidence_score.is_(None), QueryLog.confidence_score <= 0.40)
        )

    recent_rows = (await session.execute(recent_query.limit(20))).scalars().all()
    recent_items: list[RecentQueryItem] = [
        RecentQueryItem(
            id=r.id,
            question=r.question,
            answer_preview=(
                (r.answer[:140] + "...") if r.answer and len(r.answer) > 140 else r.answer
            ),
            confidence_score=float(r.confidence_score) if r.confidence_score is not None else None,
            feedback=r.feedback,
            created_at=r.created_at,
        )
        for r in recent_rows
    ]

    # 6. Confidence distribution
    high_count = (
        await session.execute(
            select(func.count(QueryLog.id)).where(QueryLog.confidence_score >= 0.65)
        )
    ).scalar() or 0
    med_count = (
        await session.execute(
            select(func.count(QueryLog.id)).where(
                QueryLog.confidence_score >= 0.40,
                QueryLog.confidence_score < 0.65,
            )
        )
    ).scalar() or 0
    low_count = (
        await session.execute(
            select(func.count(QueryLog.id)).where(
                or_(QueryLog.confidence_score.is_(None), QueryLog.confidence_score < 0.40)
            )
        )
    ).scalar() or 0

    confidence_dist = ConfidenceTierBreakdown(
        high_count=high_count,
        medium_count=med_count,
        low_count=low_count,
        high_percentage=round((high_count / total_queries) * 100, 1) if total_queries > 0 else 0.0,
        medium_percentage=round((med_count / total_queries) * 100, 1) if total_queries > 0 else 0.0,
        low_percentage=round((low_count / total_queries) * 100, 1) if total_queries > 0 else 0.0,
    )

    return AnalyticsResponse(
        total_queries=total_queries,
        total_documents=total_docs,
        total_chunks=total_chunks,
        total_sources=total_sources,
        unresolved_conflicts=unresolved_conflicts,
        feedback_stats={
            "up_count": up_count,
            "down_count": down_count,
            "unrated_count": unrated_count,
            "positive_feedback_rate": round(positive_rate, 1),
        },
        fallback_rate=round(fallback_rate, 1),
        recent_queries=recent_items,
        top_fallback_questions=list(fallback_questions),
        confidence_distribution=confidence_dist,
    )


@router.get("/analytics/export")
async def export_query_logs_csv(
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Export all student query logs as a CSV download."""
    stmt = select(QueryLog).order_by(QueryLog.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["ID", "Timestamp (UTC)", "Question", "Answer Preview", "Confidence Score", "Feedback"]
    )

    for r in rows:
        writer.writerow(
            [
                str(r.id),
                r.created_at.isoformat(),
                r.question,
                (r.answer[:200] + "...") if r.answer and len(r.answer) > 200 else (r.answer or ""),
                float(r.confidence_score) if r.confidence_score is not None else "",
                r.feedback or "unrated",
            ]
        )

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=edusync_queries_export.csv"},
    )


# ---------------------------------------------------------------------------
# 5. System Tools & Maintenance Endpoints
# ---------------------------------------------------------------------------
@router.get("/tools/health", response_model=SystemHealthResponse)
async def get_system_tools_health(
    session: AsyncSession = Depends(get_db),
) -> SystemHealthResponse:
    """Inspect database latency, pgvector extension, and knowledge base counts."""
    import time

    from sqlalchemy import text

    t0 = time.perf_counter()
    await session.execute(text("SELECT 1"))
    ping_ms = round((time.perf_counter() - t0) * 1000, 2)

    pgvector_res = await session.execute(
        text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
    )
    pgvector_ok = bool(pgvector_res.scalar() or 0)

    total_docs = (await session.execute(select(func.count(Document.id)))).scalar() or 0
    total_chunks = (await session.execute(select(func.count(Chunk.id)))).scalar() or 0
    total_sources = (await session.execute(select(func.count(IngestionSource.id)))).scalar() or 0
    unresolved_conflicts = (
        await session.execute(select(func.count(Conflict.id)).where(Conflict.resolved_at.is_(None)))
    ).scalar() or 0

    return SystemHealthResponse(
        status="healthy",
        db_ping_ms=ping_ms,
        total_documents=total_docs,
        total_chunks=total_chunks,
        total_sources=total_sources,
        unresolved_conflicts=unresolved_conflicts,
        pgvector_installed=pgvector_ok,
    )


@router.post("/tools/rag-playground", response_model=RAGPlaygroundResponse)
async def rag_playground_search(
    payload: RAGPlaygroundRequest,
    session: AsyncSession = Depends(get_db),
) -> RAGPlaygroundResponse:
    """Run an isolated retrieval diagnostic without logging to student history."""
    import time

    from retrieval.confidence_gate import ConfidenceGate
    from retrieval.hybrid_search import HybridSearcher
    from retrieval.reranker import CrossEncoderReranker

    start_t = time.perf_counter()
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    searcher = HybridSearcher()
    depts = (
        [payload.department] if payload.department and payload.department.lower() != "all" else None
    )

    retrieved = await searcher.search(
        session=session,
        query=query,
        top_k=20,
        departments=depts,
    )

    reranker = CrossEncoderReranker()
    reranked = reranker.rerank(query=query, chunks=retrieved, top_k=payload.top_k)

    gate = ConfidenceGate()
    gate_res = gate.evaluate(reranked)

    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)

    diag_chunks: list[DiagnosticChunkItem] = []
    for rank, ch in enumerate(reranked, start=1):
        diag_chunks.append(
            DiagnosticChunkItem(
                chunk_id=ch.chunk_id,
                document_id=ch.document_id,
                title=getattr(ch, "document_title", None) or "Notice Chunk",
                department=ch.department,
                source_url=ch.source_url or "",
                content_snippet=ch.content[:240] + ("..." if len(ch.content) > 240 else ""),
                vector_score=round(ch.vector_score, 4) if ch.vector_score is not None else None,
                keyword_score=round(ch.keyword_score, 4) if ch.keyword_score is not None else None,
                rrf_score=round(ch.score, 4) if ch.score is not None else 0.0,
                rerank_score=round(ch.rerank_score, 4) if ch.rerank_score is not None else None,
                rank=rank,
            )
        )

    return RAGPlaygroundResponse(
        query=query,
        execution_time_ms=elapsed_ms,
        passed_gate=gate_res.passed,
        confidence_level=gate_res.confidence_level.value,
        confidence_score=round(gate_res.top_score, 3),
        is_fallback=gate_res.is_fallback,
        fallback_message=gate_res.fallback_message,
        chunks=diag_chunks,
    )


@router.post("/tools/sync-all-sources")
async def trigger_full_corpus_sync() -> dict:
    """Trigger sequential ingestion across all active prioritized sources."""
    from ingestion.tasks import fetch_all_sources_task

    fetch_all_sources_task.delay()
    return {
        "status": "success",
        "message": "Corpus synchronization initiated via Celery worker.",
    }
