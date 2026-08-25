import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from ingestion.fetchers.ecajmer_fetcher import ECAjmerFetcher
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
    initial_fetch_limit: int = Field(50, description="Max notices to fetch on first run")
    subsequent_fetch_limit: int = Field(20, description="Max notices to fetch on recurring runs")


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

    asyncio.create_task(_run_fetch_source(str(source_id)))

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
    default_sources = [
        # High Priority: CSE, Examination, Registrar
        (
            "CSE Circulars",
            "https://www.ecajmer.ac.in/departments/cs-it/circulars",
            "Computer Science and Engineering",
            "circulars",
            "cs-it",
        ),
        (
            "CSE Time Tables",
            "https://www.ecajmer.ac.in/departments/cs-it/timetable",
            "Computer Science and Engineering",
            "timetable",
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
            "Academic Section",
            "https://www.ecajmer.ac.in/ui/cells/academic-section/circulars",
            "Academic Section",
            "circulars",
            "academic-section",
        ),
        # Other Engineering Departments
        (
            "Civil Engineering Circulars",
            "https://www.ecajmer.ac.in/departments/ce/circulars",
            "Civil Engineering",
            "circulars",
            "ce",
        ),
        (
            "Electrical Engineering Circulars",
            "https://www.ecajmer.ac.in/departments/ee/circulars",
            "Electrical Engineering",
            "circulars",
            "ee",
        ),
        (
            "Electronics & Communication Circulars",
            "https://www.ecajmer.ac.in/departments/ece/circulars",
            "Electronics and Communication Engineering",
            "circulars",
            "ece",
        ),
        (
            "Mechanical Engineering Circulars",
            "https://www.ecajmer.ac.in/departments/me/circulars",
            "Mechanical Engineering",
            "circulars",
            "me",
        ),
        (
            "EIC Department Circulars",
            "https://www.ecajmer.ac.in/departments/eic/circulars",
            "Electronic Instrumentation And Control Engineering",
            "circulars",
            "eic",
        ),
        (
            "MCA Department Circulars",
            "https://www.ecajmer.ac.in/departments/mca/circulars",
            "Computer Applications",
            "circulars",
            "mca",
        ),
        (
            "MBA Department Circulars",
            "https://www.ecajmer.ac.in/departments/mba/circulars",
            "Management Studies",
            "circulars",
            "mba",
        ),
        (
            "Applied Sciences (Physics/Chem/Maths)",
            "https://www.ecajmer.ac.in/departments/physics/circulars",
            "Physics",
            "circulars",
            "physics",
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
                initial_fetch_limit=50,
                subsequent_fetch_limit=20,
                status="idle",
            )
            session.add(src)

    await session.commit()
    return await list_sources(session)
