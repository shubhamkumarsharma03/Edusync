import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.hasher import compute_hash
from ingestion.schemas import FetchedDocument
from models.document import Document


class ChangeStatus(StrEnum):
    """Document change detection status."""

    NEW = "NEW"
    UNCHANGED = "UNCHANGED"
    MODIFIED = "MODIFIED"


class DetectionResult(BaseModel):
    """Result of document change detection check."""

    source_url: str
    status: ChangeStatus
    content_hash: str
    existing_document_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def requires_reembedding(self) -> bool:
        """Indicates if downstream chunking & vector embedding is required."""
        return self.status in (ChangeStatus.NEW, ChangeStatus.MODIFIED)


class ChangeDetector:
    """Detects content modifications via SHA-256 hash comparison against PostgreSQL."""

    @staticmethod
    async def check_document(
        session: AsyncSession,
        fetched: FetchedDocument,
        department: str | None = None,
        owner: str | None = None,
    ) -> DetectionResult:
        """Compare fetched document against stored content_hash.

        - If not in DB: Status -> NEW
        - If hash matches: Status -> UNCHANGED, updates last_checked_at
        - If hash differs: Status -> MODIFIED, marks status='pending'
        """
        computed_hash = compute_hash(fetched.raw_content, source_type=fetched.source_type)

        stmt = select(Document).where(Document.source_url == fetched.source_url)
        result = await session.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc is None:
            return DetectionResult(
                source_url=fetched.source_url,
                status=ChangeStatus.NEW,
                content_hash=computed_hash,
                metadata={
                    "department": department or fetched.metadata.get("department"),
                    "owner": owner or fetched.metadata.get("owner"),
                },
            )

        now = datetime.now(UTC)

        if existing_doc.content_hash == computed_hash:
            existing_doc.last_checked_at = now
            await session.commit()
            return DetectionResult(
                source_url=fetched.source_url,
                status=ChangeStatus.UNCHANGED,
                content_hash=computed_hash,
                existing_document_id=existing_doc.id,
                metadata={"status": existing_doc.status},
            )
        else:
            existing_doc.status = "pending"
            existing_doc.last_checked_at = now
            await session.commit()
            return DetectionResult(
                source_url=fetched.source_url,
                status=ChangeStatus.MODIFIED,
                content_hash=computed_hash,
                existing_document_id=existing_doc.id,
                metadata={"previous_hash": existing_doc.content_hash},
            )

    @classmethod
    async def check_batch(
        cls,
        session: AsyncSession,
        documents: list[FetchedDocument],
    ) -> list[DetectionResult]:
        """Process a list of fetched documents in batch."""
        results: list[DetectionResult] = []
        for doc in documents:
            res = await cls.check_document(session, doc)
            results.append(res)
        return results
