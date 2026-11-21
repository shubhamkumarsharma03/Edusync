from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Index, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDMixin


class Student(Base, UUIDMixin):
    __tablename__ = "students"

    college_roll_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    semester: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    degree: Mapped[str] = mapped_column(String(50), nullable=False, default="B.Tech")
    admission_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("semester BETWEEN 1 AND 8", name="ck_students_semester"),
        CheckConstraint("degree IN ('B.Tech', 'M.Tech', 'MCA', 'MBA')", name="ck_students_degree"),
        CheckConstraint("role IN ('student', 'admin')", name="ck_students_role"),
        Index("ix_students_branch_semester", "branch", "semester"),
        Index("ix_students_roll_no", func.upper(college_roll_no)),
        Index("ix_students_email", func.lower(email)),
    )
