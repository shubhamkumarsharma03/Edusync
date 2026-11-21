import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDMixin


class QueryFeedback(Base, UUIDMixin):
    __tablename__ = "query_feedback"

    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries_log.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
    )
    feedback_type: Mapped[str] = mapped_column(String(10), nullable=False)
    issue_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    student_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="unreviewed")

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            feedback_type.in_(["up", "down"]),
            name="ck_query_feedback_type",
        ),
        Index("ix_query_feedback_query", "query_id"),
        Index("ix_query_feedback_student", "student_id"),
    )
