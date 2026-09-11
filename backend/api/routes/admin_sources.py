import logging
import re
from datetime import datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from ingestion.fetchers.ecajmer_fetcher import ECAjmerFetcher
from models.chunk import Chunk
from models.document import Document
from models.source import IngestionSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/sources", tags=["Admin Sources"])


class SourceBase(BaseModel):
    name: str = Field(..., description="Display name for the source")
    url: str = Field(..., description="Source URL on ecajmer.ac.in or institutional portal")
    department: str | None = Field(None, description="Associated department name")
    category: str = Field("circulars", description="Notice category: circulars or timetable")
    slug: str | None = Field(None, description="URL slug e.g. cs-it, ce, registrar")
    priority: int | None = Field(None, description="Sequential priority rank (1, 2, 3...)")
    is_active: bool = Field(True, description="Whether source is enabled for scheduled ingestion")
    initial_fetch_limit: int = Field(10, description="Max notices to fetch on first run")
    subsequent_fetch_limit: int = Field(5, description="Max notices to fetch on recurring runs")


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    department: str | None = None
    category: str | None = None
    slug: str | None = None
    priority: int | None = None
    is_active: bool | None = None
    initial_fetch_limit: int | None = None
    subsequent_fetch_limit: int | None = None


class SourceResponse(SourceBase):

    id: UUID
    priority: int
    status: str
    error_message: str | None = None
    last_fetched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReorderItem(BaseModel):
    id: UUID
    priority: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem]


class IngestedDocumentResponse(BaseModel):
    id: UUID
    source_url: str
    source_type: str
    department: str | None = None
    title: str
    notice_sno: str | None = None
    notice_date: str | None = None
    content_hash: str
    status: str
    chunk_count: int
    ingested_at: datetime
    last_checked_at: datetime
    preview: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SourceDocumentsListResponse(BaseModel):
    total: int
    page: int
    limit: int
    source_id: UUID
    source_name: str
    documents: list[IngestedDocumentResponse]


class DocumentChunkDetail(BaseModel):
    id: UUID
    token_count: int
    last_verified: datetime
    content: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[SourceResponse])
async def list_sources(session: AsyncSession = Depends(get_db)) -> list[IngestionSource]:
    """Retrieve all ingestion sources sorted by priority ASC."""
    stmt = select(IngestionSource).order_by(
        IngestionSource.priority.asc(), IngestionSource.created_at.asc()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    session: AsyncSession = Depends(get_db),
) -> IngestionSource:
    """Create a new prioritized ingestion source URL."""
    # Auto-assign next priority if not provided
    if payload.priority is None:
        max_priority_stmt = select(func.max(IngestionSource.priority))
        max_res = await session.execute(max_priority_stmt)
        curr_max = max_res.scalar()
        priority_val = (curr_max or 0) + 1
    else:
        priority_val = payload.priority

    # Auto-extract slug and department if missing
    slug_val = payload.slug
    dept_val = payload.department
    cat_val = payload.category

    if not slug_val or not dept_val:
        extracted_slug, cat_id, extracted_dept = ECAjmerFetcher.parse_url(payload.url)
        slug_val = slug_val or extracted_slug
        dept_val = dept_val or extracted_dept
        if not payload.category:
            cat_val = "timetable" if cat_id == 2 else "circulars"

    new_source = IngestionSource(
        name=payload.name,
        url=payload.url,
        department=dept_val,
        category=cat_val,
        slug=slug_val,
        priority=priority_val,
        is_active=payload.is_active,
        initial_fetch_limit=payload.initial_fetch_limit,
        subsequent_fetch_limit=payload.subsequent_fetch_limit,
        status="idle",
    )

    session.add(new_source)
    await session.commit()
    await session.refresh(new_source)
    return new_source


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> IngestionSource:
    """Get a single source by ID."""
    stmt = select(IngestionSource).where(IngestionSource.id == source_id)
    res = await session.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    payload: SourceUpdate,
    session: AsyncSession = Depends(get_db),
) -> IngestionSource:
    """Update an existing source."""
    stmt = select(IngestionSource).where(IngestionSource.id == source_id)
    res = await session.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    await session.commit()
    await session.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a source."""
    stmt = select(IngestionSource).where(IngestionSource.id == source_id)
    res = await session.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    await session.delete(source)
    await session.commit()


@router.post("/reorder", response_model=list[SourceResponse])
async def reorder_sources(
    payload: ReorderRequest,
    session: AsyncSession = Depends(get_db),
) -> list[IngestionSource]:
    """Batch reorder source priorities."""
    for item in payload.items:
        stmt = select(IngestionSource).where(IngestionSource.id == item.id)
        res = await session.execute(stmt)
        src = res.scalar_one_or_none()
        if src:
            src.priority = item.priority

    await session.commit()
    return await list_sources(session)


@router.post("/{source_id}/fetch")
async def trigger_source_fetch(
    source_id: UUID,
    limit: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger ingestion for a single source immediately."""
    stmt = select(IngestionSource).where(IngestionSource.id == source_id)
    res = await session.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Launch background task in-process asynchronously
    import asyncio

    from ingestion.tasks import _run_fetch_source

    asyncio.create_task(_run_fetch_source(str(source_id), limit=limit))

    return {
        "status": "triggered",
        "source_id": str(source_id),
        "source_name": source.name,
        "task_id": f"in_process_{source_id}",
    }


@router.post("/fetch-all")
async def trigger_fetch_all() -> dict:
    """Trigger prioritized ingestion across all active sources."""
    import asyncio

    from ingestion.tasks import _run_fetch_all_sources_by_priority

    asyncio.create_task(_run_fetch_all_sources_by_priority())

    return {
        "status": "triggered",
        "task_id": "in_process_batch",
        "message": "Prioritized batch ingestion queued for all active sources.",
    }


@router.post("/seed-defaults", response_model=list[SourceResponse])
async def seed_default_sources(
    session: AsyncSession = Depends(get_db),
) -> list[IngestionSource]:
    """One-click preload all official departments and sections from ecajmer.ac.in."""
    # Keep 4 core links hardcoded for instant prefetching & seeding
    default_sources = [
        (
            "CSE Circulars",
            "https://www.ecajmer.ac.in/departments/cs-it/circulars",
            "Computer Science and Engineering",
            "circulars",
            "cs-it",
        ),
        (
            "Examination Section Circulars",
            "https://www.ecajmer.ac.in/ui/cells/examination-section/circulars",
            "Examination Section",
            "circulars",
            "examination-section",
        ),
        (
            "Registrar Circulars",
            "https://www.ecajmer.ac.in/ui/cells/registrar/circulars",
            "Registrar Section",
            "circulars",
            "registrar",
        ),
        (
            "Academic Section Notices",
            "https://www.ecajmer.ac.in/ui/cells/academic-section/circulars",
            "Academic Section",
            "circulars",
            "academic-section",
        ),
    ]

    for idx, (name, url, dept, cat, slug) in enumerate(default_sources, start=1):
        # Check if already exists
        check_stmt = select(IngestionSource).where(IngestionSource.url == url)
        existing = (await session.execute(check_stmt)).scalar_one_or_none()
        if not existing:
            src = IngestionSource(
                name=name,
                url=url,
                department=dept,
                category=cat,
                slug=slug,
                priority=idx,
                initial_fetch_limit=10,
                subsequent_fetch_limit=5,
                status="idle",
                is_active=True,
            )
            session.add(src)

    await session.commit()
    return await list_sources(session)


def _extract_notice_meta(
    chunks: list[Chunk], source_url: str
) -> tuple[str, str | None, str | None, str | None]:
    """Extract human-readable notice title, S.No, and date from chunk content."""
    title, sno, date, preview = None, None, None, None
    for c in chunks:
        if not preview and c.content:
            preview = c.content[:300].strip()
        if not title:
            m = re.search(r"^#\s+([^#\n\r]+)$", c.content, re.MULTILINE)
            if m:
                candidate = m.group(1).strip()
                if not candidate.lower().startswith("table"):
                    title = candidate
        if not sno:
            m = re.search(r"\*\*Notice S\.No:\*\*\s*([^\n\r]+)", c.content)
            if m:
                sno = m.group(1).strip()
        if not date:
            m = re.search(r"\*\*Date:\*\*\s*([^\n\r]+)", c.content)
            if m:
                date = m.group(1).strip()
        if title and sno and date and preview:
            break

    if not title:
        fname = source_url.split("/")[-1]
        title = fname or source_url

    return title, sno, date, preview


@router.get("/{source_id}/documents", response_model=SourceDocumentsListResponse)
async def list_source_documents(
    source_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> SourceDocumentsListResponse:
    """Retrieve documents stored in PostgreSQL DB that were ingested for this source."""
    stmt = select(IngestionSource).where(IngestionSource.id == source_id)
    res = await session.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    conds = []
    if source.department:
        conds.append(Document.department.ilike(f"%{source.department}%"))
        if "computer" in source.department.lower():
            conds.append(Document.department.ilike("%cse%"))
    if source.url:
        conds.append(Document.source_url.ilike(f"%{source.url}%"))

    base_filter = or_(*conds) if conds else (Document.source_url != "")

    if search and search.strip():
        term = f"%{search.strip()}%"
        matching_subq = (
            select(Document.id)
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .where(
                base_filter,
                or_(
                    Document.source_url.ilike(term),
                    Document.department.ilike(term),
                    Chunk.content.ilike(term),
                ),
            )
            .distinct()
        )
        base_query = select(Document).where(Document.id.in_(matching_subq))
    else:
        base_query = select(Document).where(base_filter)

    count_stmt = select(func.count()).select_from(base_query.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * limit
    paginated_stmt = (
        base_query.order_by(Document.ingested_at.desc(), Document.last_checked_at.desc())
        .offset(offset)
        .limit(limit)
    )
    docs = (await session.execute(paginated_stmt)).scalars().all()

    doc_items: list[IngestedDocumentResponse] = []
    for d in docs:
        chunk_stmt = select(Chunk).where(Chunk.document_id == d.id).order_by(Chunk.id.asc())
        chunks = (await session.execute(chunk_stmt)).scalars().all()
        title, sno, date, preview = _extract_notice_meta(chunks, d.source_url)
        doc_items.append(
            IngestedDocumentResponse(
                id=d.id,
                source_url=d.source_url,
                source_type=d.source_type,
                department=d.department,
                title=title,
                notice_sno=sno,
                notice_date=date,
                content_hash=d.content_hash,
                status=d.status,
                chunk_count=len(chunks),
                ingested_at=d.ingested_at,
                last_checked_at=d.last_checked_at,
                preview=preview,
            )
        )

    return SourceDocumentsListResponse(
        total=total,
        page=page,
        limit=limit,
        source_id=source.id,
        source_name=source.name,
        documents=doc_items,
    )


@router.get("/{source_id}/documents/{document_id}/chunks", response_model=list[DocumentChunkDetail])
async def get_document_chunks(
    source_id: UUID,
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DocumentChunkDetail]:
    """Retrieve full text chunks and embeddings metadata for a specific ingested document."""
    doc_stmt = select(Document).where(Document.id == document_id)
    doc = (await session.execute(doc_stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks_stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.id.asc())
    chunks = (await session.execute(chunks_stmt)).scalars().all()
    return [
        DocumentChunkDetail(
            id=c.id,
            token_count=c.token_count,
            last_verified=c.last_verified,
            content=c.content,
        )
        for c in chunks
    ]


@router.get("/{source_id}/live-feed")
async def get_source_live_feed(
    source_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str = Query(""),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Safely proxy live notices from ECA portal on the backend without browser CORS blocks."""
    stmt = select(IngestionSource).where(IngestionSource.id == source_id)
    source = (await session.execute(stmt)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    slug = source.slug or "cs-it"
    category_id = 2 if source.category == "timetable" else 1
    remote_url = (
        f"https://ecajmer.ac.in/api/circulars/public/{slug}"
        f"?page={page}&limit={limit}&mainCategoryId={category_id}&search={search}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(remote_url)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"Could not fetch live feed from {remote_url}: {e}")

    return {"success": False, "data": [], "pagination": {"totalItems": 0}}
