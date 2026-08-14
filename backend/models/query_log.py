import uuid
from datetime import datetime
from sqlalchemy import Text, Numeric, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP, ARRAY, UUID

from db.base import Base, UUIDMixin

class QueryLog(Base, UUIDMixin):
    __tablename__ = "queries_log"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            feedback.in_(["up", "down"]),
            name="queries_log_feedback_check",
        ),
    )
