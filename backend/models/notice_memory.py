"""NoticeMemory model — structured notice metadata extracted via Gemini API.

Stores per-notice analysis results: department, year, branch, semester,
content fingerprint, key facts, and the is_latest supersession flag.
See docs/memory_system_plan.md for design rationale.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, UUIDMixin


class NoticeMemory(Base, UUIDMixin):
    """Structured notice metadata extracted by a single Gemini API call per ingested document.

    This table is the backbone of the Memory System:
    - Enables per-department / per-year / per-branch scoped retrieval.
    - Tracks supersession (newer notice replaces older one with same content_fingerprint).
    - Stores key_facts for fast-path direct answer retrieval.
    """

    __tablename__ = "notice_memory"

    # FK to the parent document
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # --- Gemini-extracted structured fields ---
    notice_type: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_year: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    target_semester: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    target_branch: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    academic_session: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_serial: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_facts: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="'[]'::jsonb")
    content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Supersession tracking ---
    is_latest: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notice_memory.id", ondelete="SET NULL"), nullable=True
    )
    supersession_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Metadata ---
    analyzed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    gemini_model: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="'gemini-2.5-flash'"
    )
    raw_llm_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id])
    superseded_by_memory: Mapped["NoticeMemory | None"] = relationship(
        "NoticeMemory", remote_side="NoticeMemory.id", foreign_keys=[superseded_by]
    )

    __table_args__ = (
        Index("idx_notice_memory_fingerprint", "content_fingerprint"),
        Index("idx_notice_memory_latest", "is_latest", postgresql_where=is_latest.is_(True)),
        Index("idx_notice_memory_dept_type", "department", "notice_type"),
    )


# Avoid circular import at module level
from models.document import Document  # noqa: E402, F811
