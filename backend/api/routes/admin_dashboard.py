import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
        description="Resolution strategy: 'supersede', 'non_conflicting', or 'dismiss'",
    )
    notes: str | None = None


# --- Analytics Schemas ---
class RecentQueryItem(BaseModel):
    id: UUID
    question: str
    answer_preview: str | None = None
    confidence_score: float | None = None
    feedback: str | None = None
    created_at: datetime


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
                Document.source_url.ilike(term),
                Document.notice_sno.ilike(term),
            )
        )

    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    # Paginate using chronological portal order
    offset = (page - 1) * limit
    paginated_query = (
        query.order_by(
            Document.notice_date.desc().nullslast(),
            Document.notice_sno.desc().nullslast(),
            Document.portal_id.desc().nullslast(),
            Document.ingested_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    docs = (await session.execute(paginated_query)).scalars().all()

    # Fetch chunk counts in bulk
    doc_ids = [d.id for d in docs]
    chunk_counts: dict[UUID, int] = {}
    if doc_ids:
        chunk_count_stmt = (
            select(Chunk.document_id, func.count(Chunk.id))
            .where(Chunk.document_id.in_(doc_ids))
            .group_by(Chunk.document_id)
        )
        counts = (await session.execute(chunk_count_stmt)).all()
        chunk_counts = {r[0]: r[1] for r in counts}

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
    """Resolve a conflict by marking one document authoritative or marking non-conflicting."""
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
    elif res_type == "non_conflicting":
        # Both/all documents are valid (e.g. Sem 3 vs Sem 7 fee order)
        for d in docs:
            d.status = "fresh"
        conflict.resolution_note = f"Verified non-conflicting by admin. {note}"
    else:
        # Dismiss conflict, keep current statuses
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


# ---------------------------------------------------------------------------
# 4. Analytics & Health Panel
# ---------------------------------------------------------------------------
@router.get("/analytics", response_model=AnalyticsResponse)
async def get_admin_analytics(
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

    # 5. Recent Queries
    recent_stmt = select(QueryLog).order_by(QueryLog.created_at.desc()).limit(10)
    recent_rows = (await session.execute(recent_stmt)).scalars().all()
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
    )
