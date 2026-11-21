from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.department import Department

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, UUIDMixin


class Document(Base, UUIDMixin):
    __tablename__ = "documents"

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    department_rel: Mapped["Department"] = relationship(lazy="selectin")
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="fresh")

    # College portal ordering and publication metadata
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice_sno: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    portal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ingested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def department(self) -> str | None:
        """Helper property to access department name if relationship is loaded."""
        try:
            return self.department_rel.name if self.department_rel else None
        except Exception:
            return None

    __table_args__ = (
        CheckConstraint(
            source_type.in_(["pdf", "html", "sheet"]), name="documents_source_type_check"
        ),
        CheckConstraint(
            status.in_(["fresh", "stale", "conflicted", "pending", "archived"]),
            name="documents_status_check",
        ),
    )
