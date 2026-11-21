import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDMixin


class QueryLog(Base, UUIDMixin):
    __tablename__ = "queries_log"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Expanded Telemetry & Relational Linkage
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewritten_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieval_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            feedback.in_(["up", "down"]),
            name="queries_log_feedback_check",
        ),
        Index("ix_queries_log_session", "session_id"),
        Index("ix_queries_log_student", "student_id"),
        Index("ix_queries_log_fallback", "is_fallback", "created_at"),
    )
