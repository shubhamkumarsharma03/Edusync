import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.department import Department

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/departments", tags=["Admin Departments"])


class DepartmentBase(BaseModel):
    name: str = Field(..., description="Full official department or section name")
    code: str | None = Field(None, description="Short code, e.g. CSE, EXAM, REG")
    category: str = Field(
        "Engineering",
        description="Category group, e.g. Engineering, Administration, Sciences, Student Services",
    )
    slug: str | None = Field(None, description="URL slug or identifier e.g. cs-it, registrar")
    is_active: bool = Field(True, description="Whether department is actively displayed")


class DepartmentCreate(DepartmentBase):
    id: int | None = Field(None, description="Optional custom integer ID")


class DepartmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    category: str | None = None
    slug: str | None = None
    is_active: bool | None = None


class DepartmentResponse(DepartmentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    category: str | None = Query(None, description="Filter by category group"),
    active_only: bool = Query(True, description="Only return active departments"),
    session: AsyncSession = Depends(get_db),
) -> list[Department]:
    """Retrieve all departments and administrative sections with simple integer IDs."""
    stmt = select(Department).order_by(Department.id.asc())
    if active_only:
        stmt = stmt.where(Department.is_active == True)  # noqa: E712
    if category:
        stmt = stmt.where(Department.category == category)

    res = await session.execute(stmt)
    return list(res.scalars().all())


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    session: AsyncSession = Depends(get_db),
) -> Department:
    """Create a new department or section dynamically with simple integer ID."""
    # Check if name already exists
    exists_stmt = select(Department).where(Department.name.ilike(payload.name.strip()))
    existing = (await session.execute(exists_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department with name '{payload.name}' already exists (ID: {existing.id})",
        )

    computed_slug = (
        payload.slug.strip()
        if payload.slug
        else payload.name.strip().lower().replace(" ", "-")
    )

    dept_kwargs = {
        "name": payload.name.strip(),
        "code": payload.code.strip() if payload.code else None,
        "category": payload.category.strip(),
        "slug": computed_slug,
        "is_active": payload.is_active,
    }
    if payload.id is not None:
        dept_kwargs["id"] = payload.id

    dept = Department(**dept_kwargs)
    session.add(dept)
    await session.commit()
    await session.refresh(dept)
    logger.info(f"Created department ID {dept.id}: {dept.name}")
    return dept


@router.get("/{dept_id}", response_model=DepartmentResponse)
async def get_department(
    dept_id: int,
    session: AsyncSession = Depends(get_db),
) -> Department:
    """Retrieve single department details by simple integer ID."""
    stmt = select(Department).where(Department.id == dept_id)
    dept = (await session.execute(stmt)).scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept


@router.put("/{dept_id}", response_model=DepartmentResponse)
async def update_department(
    dept_id: int,
    payload: DepartmentUpdate,
    session: AsyncSession = Depends(get_db),
) -> Department:
    """Update department details."""
    stmt = select(Department).where(Department.id == dept_id)
    dept = (await session.execute(stmt)).scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dept, field, value)

    await session.commit()
    await session.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    dept_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete or deactivate department."""
    stmt = select(Department).where(Department.id == dept_id)
    dept = (await session.execute(stmt)).scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    await session.delete(dept)
    await session.commit()
