from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, UUIDMixin


class IngestionSource(Base, UUIDMixin):
    """Stores prioritized institutional source URLs (e.g. department circulars, timetables)."""

    __tablename__ = "ingestion_sources"

    url: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default="circulars")
    slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    initial_fetch_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, server_default="50"
    )
    subsequent_fetch_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20, server_default="20"
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="idle")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            status.in_(["idle", "fetching", "completed", "error"]),
            name="ingestion_sources_status_check",
        ),
    )
