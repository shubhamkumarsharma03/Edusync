import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth_utils import (
    create_access_token,
    get_current_student,
    hash_password,
    verify_password,
)
from db.session import get_db
from models.student import Student

router = APIRouter(prefix="/auth", tags=["Authentication & Student Profiles"])


class StudentRegisterRequest(BaseModel):
    college_roll_no: str = Field(
        ..., min_length=3, max_length=50, description="College roll number e.g. 21ECA045"
    )
    email: str = Field(..., min_length=5, max_length=255, description="College or personal email")
    full_name: str = Field(..., min_length=2, max_length=150, description="Full student name")
    branch: str = Field(
        ..., min_length=2, max_length=100, description="Academic department or branch"
    )
    semester: int = Field(
        ..., ge=1, le=8, description="Current semester (1-8 for B.Tech, 1-4 for Masters)"
    )
    degree: str = Field("B.Tech", description="Academic degree e.g. B.Tech, MCA, MBA")
    admission_year: int = Field(2021, ge=2015, le=2030, description="Year of admission")
    password: str = Field(..., min_length=6, max_length=100, description="Account password")


class StudentLoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, description="Roll number or email address")
    password: str = Field(..., min_length=1, description="Account password")


class StudentProfileResponse(BaseModel):
    id: uuid.UUID
    college_roll_no: str
    email: str
    full_name: str
    branch: str
    semester: int
    degree: str
    admission_year: int
    role: str
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student: StudentProfileResponse


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
async def register_student(
    payload: StudentRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new student account with validated college roll number, branch, and semester."""
    clean_name = payload.full_name.strip()
    clean_roll = payload.college_roll_no.strip().upper()
    clean_email = payload.email.strip().lower()
    clean_branch = payload.branch.strip()

    # 1. Name validation
    if not re.match(r"^[A-Za-z\s.'-]{2,100}$", clean_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name must only contain letters, spaces, dots, and hyphens.",
        )

    # 2. Roll number validation
    if not re.match(r"^[A-Z0-9-]{4,25}$", clean_roll):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Roll number must be alphanumeric (e.g. 21ECA045 or 24MBA05).",
        )

    # 3. Email validation
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address.",
        )

    # 4. Program Degree & Semester bounds validation (Masters = max 4 sems, B.Tech = max 8 sems)
    is_masters = (
        clean_branch in ("Master of Computer Applications", "Master of Business Administration")
        or "master" in clean_branch.lower()
        or "mca" in clean_branch.lower()
        or "mba" in clean_branch.lower()
    )

    if is_masters:
        if payload.semester < 1 or payload.semester > 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Masters programs ({clean_branch}) have a maximum of 4 semesters (Sem 1 to Sem 4).",
            )
        resolved_degree = "MCA" if "computer" in clean_branch.lower() else "MBA"
    else:
        if payload.semester < 1 or payload.semester > 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="B.Tech programs have a maximum of 8 semesters (Sem 1 to Sem 8).",
            )
        resolved_degree = "B.Tech"

    # 5. Password length check
    if len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long.",
        )

    # Check for existing student with same roll number or email
    stmt = select(Student).where(
        or_(
            func.upper(Student.college_roll_no) == clean_roll,
            func.lower(Student.email) == clean_email,
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        if existing.college_roll_no.upper() == clean_roll:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A student with roll number '{clean_roll}' is already registered.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A student with email '{clean_email}' is already registered.",
            )

    student = Student(
        college_roll_no=clean_roll,
        email=clean_email,
        full_name=clean_name,
        branch=clean_branch,
        semester=payload.semester,
        degree=resolved_degree,
        admission_year=payload.admission_year,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_verified=True,
        role="student",
        last_login_at=datetime.now(),
    )

    db.add(student)
    await db.commit()
    await db.refresh(student)

    token = create_access_token(
        {
            "sub": str(student.id),
            "roll_no": student.college_roll_no,
            "role": student.role,
        }
    )

    profile = StudentProfileResponse(
        id=student.id,
        college_roll_no=student.college_roll_no,
        email=student.email,
        full_name=student.full_name,
        branch=student.branch,
        semester=student.semester,
        degree=student.degree,
        admission_year=student.admission_year,
        role=student.role,
        created_at=student.created_at,
    )

    return AuthResponse(access_token=token, student=profile)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in with college roll number or email",
)
async def login_student(
    payload: StudentLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate student using institutional credentials."""
    clean_id = payload.identifier.strip()
    if len(clean_id) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid roll number or email address.",
        )
    if not payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password cannot be empty.",
        )
    stmt = select(Student).where(
        or_(
            func.upper(Student.college_roll_no) == clean_id.upper(),
            func.lower(Student.email) == clean_id.lower(),
        )
    )
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()

    if not student or not verify_password(payload.password, student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid roll number/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student account is currently disabled.",
        )

    student.last_login_at = datetime.now()
    await db.commit()
    await db.refresh(student)

    token = create_access_token(
        {
            "sub": str(student.id),
            "roll_no": student.college_roll_no,
            "role": student.role,
        }
    )

    profile = StudentProfileResponse(
        id=student.id,
        college_roll_no=student.college_roll_no,
        email=student.email,
        full_name=student.full_name,
        branch=student.branch,
        semester=student.semester,
        degree=student.degree,
        admission_year=student.admission_year,
        role=student.role,
        created_at=student.created_at,
    )

    return AuthResponse(access_token=token, student=profile)


@router.get(
    "/me",
    response_model=StudentProfileResponse,
    summary="Retrieve current student profile",
)
async def get_me(
    student: Student = Depends(get_current_student),
) -> StudentProfileResponse:
    """Return profile details for the currently authenticated student."""
    return StudentProfileResponse(
        id=student.id,
        college_roll_no=student.college_roll_no,
        email=student.email,
        full_name=student.full_name,
        branch=student.branch,
        semester=student.semester,
        degree=student.degree,
        admission_year=student.admission_year,
        role=student.role,
        created_at=student.created_at,
    )
