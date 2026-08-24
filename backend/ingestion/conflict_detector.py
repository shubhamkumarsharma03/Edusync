import logging
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.conflict import Conflict
from models.document import Document

logger = logging.getLogger(__name__)


class ConflictDetector:
    """Detects semantic conflicts between documents during ingestion."""

    # A lightweight heuristic for document type classification based on URL/filename keywords
    TYPE_KEYWORDS: ClassVar[list[str]] = [
        "exam",
        "schedule",
        "syllabus",
        "fee",
        "timetable",
    ]

    @classmethod
    def _extract_types(cls, url: str) -> set[str]:
        url_lower = url.lower()
        return {kw for kw in cls.TYPE_KEYWORDS if kw in url_lower}

    @classmethod
    async def _check_llm_conflict(
        cls, session: AsyncSession, doc1: Document, doc2: Document
    ) -> bool:
        from google import genai

        from api.config import get_settings
        from models.chunk import Chunk

        settings = get_settings()
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key":
            logger.warning(
                "Gemini API key not set, skipping LLM conflict check and assuming conflict."
            )
            return True

        # Fetch first chunk of both documents
        stmt1 = select(Chunk.content).where(Chunk.document_id == doc1.id).limit(1)
        stmt2 = select(Chunk.content).where(Chunk.document_id == doc2.id).limit(1)

        chunk1 = (await session.execute(stmt1)).scalar_one_or_none()
        chunk2 = (await session.execute(stmt2)).scalar_one_or_none()

        if not chunk1 or not chunk2:
            return True

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = f"""
You are helping an ingestion pipeline detect conflicts between two documents. 
Both documents share the same department and source type.
Your job is to determine if they are discussing the exact same specific event or subject, but disagree on facts (like dates, versions, or amounts), which means they CONFLICT.
If they are discussing different events (e.g. Mid-Sem vs End-Sem, or 2025 vs 2026), they DO NOT conflict.

Document 1 (First part):
{chunk1[:1000]}

Document 2 (First part):
{chunk2[:1000]}

Are these two documents conflicting versions of the exact same subject? 
Reply with ONLY the word "YES" or "NO".
"""
        try:
            # Note: google-genai client methods might be synchronous, we can run them in a thread or just call it
            # The new google-genai library supports generate_content
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=prompt, config={"max_output_tokens": 10}
            )
            answer = response.text.strip().upper()
            return "YES" in answer
        except Exception as e:
            logger.error(f"LLM conflict check failed: {e}")
            return True  # Fail open to flagging a conflict

    @classmethod
    async def check_conflicts(cls, session: AsyncSession, new_doc: Document) -> bool:
        """
        Check if the newly ingested document conflicts with existing fresh documents.
        Returns True if a conflict was detected and recorded.
        """
        if not new_doc.department:
            return False

        # Only check against 'fresh' documents with the same department (excluding itself)
        stmt = select(Document).where(
            Document.status == "fresh",
            Document.department == new_doc.department,
            Document.id != new_doc.id,
        )
        result = await session.execute(stmt)
        existing_docs = result.scalars().all()

        new_doc_types = cls._extract_types(new_doc.source_url)
        has_conflict = False

        for existing_doc in existing_docs:
            existing_doc_types = cls._extract_types(existing_doc.source_url)

            # Heuristic: they share any type keywords
            shared_types = new_doc_types.intersection(existing_doc_types)

            # Simple heuristic: Same department + same source_type + matching keywords
            if existing_doc.source_type == new_doc.source_type and shared_types:
                # Use LLM to verify if it's a real conflict
                is_real_conflict = await cls._check_llm_conflict(session, new_doc, existing_doc)

                if is_real_conflict:
                    logger.warning(
                        f"Conflict detected between {new_doc.id} ({new_doc.source_url}) "
                        f"and {existing_doc.id} ({existing_doc.source_url})"
                    )
                    has_conflict = True

                    # Mark both as conflicted
                    existing_doc.status = "conflicted"
                    new_doc.status = "conflicted"

                    # Create conflict record
                    conflict = Conflict(
                        document_ids=[new_doc.id, existing_doc.id],
                        detected_at=datetime.now(UTC),
                    )
                    session.add(conflict)

        if has_conflict:
            await session.commit()
            # Refresh doc to reflect new status
            await session.refresh(new_doc)

        return has_conflict
