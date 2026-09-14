from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.department import Department

from sqlalchemy import CheckConstraint, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, UUIDMixin


class Document(Base, UUIDMixin):
    __tablename__ = "documents"

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    department_rel: Mapped["Department"] = relationship()
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="fresh")

    ingested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            source_type.in_(["pdf", "html", "sheet"]), name="documents_source_type_check"
        ),
        CheckConstraint(
            status.in_(["fresh", "stale", "conflicted", "pending"]),
            name="documents_status_check",
        ),
    )
