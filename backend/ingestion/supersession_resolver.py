"""SupersessionResolver — Detects and resolves notice supersession.

When a newer notice arrives (e.g. revised timetable or rescheduled exam):
1. Matches against existing notices with the same content_fingerprint or explicit supersession description.
2. Marks the older notices as is_latest = False and sets superseded_by pointer.
3. Ensures only the most recent version of a notice participates in default retrieval.
"""

import logging
import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.schemas import NoticeMemoryData
from models.department import Department
from models.document import Document
from models.notice_memory import NoticeMemory

logger = logging.getLogger(__name__)


class SupersessionResolver:
    """Manages notice memory records and resolves supersession relationships."""

    @classmethod
    def is_corrigendum_or_revision(cls, title: str, text: str = "") -> bool:
        """Detect if notice indicates an update, revision, amendment or postponement."""
        import re

        combined = f"{title} {text[:1000]}".lower()
        patterns = [
            r"\brevised\b",
            r"\bcorrigendum\b",
            r"\bpostponed\b",
            r"\bpostponement\b",
            r"\bamendment\b",
            r"\brescheduled?\b",
            r"\bin continuation of\b",
            r"\bextension of (?:last )?date\b",
            r"\bupdated schedule\b",
        ]
        return any(re.search(pat, combined, re.IGNORECASE) for pat in patterns)

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse date string safely."""
        if not date_str:
            return None
        clean_str = str(date_str).strip()
        try:
            if "T" in clean_str:
                clean_str = clean_str.split("T")[0]
            clean_str = clean_str.replace("/", "-")
            return date.fromisoformat(clean_str)
        except (ValueError, AttributeError):
            pass
        try:
            return datetime.strptime(clean_str, "%d-%m-%Y").date()
        except Exception:
            return None

    @classmethod
    async def resolve(
        cls,
        session: AsyncSession,
        memory_data: NoticeMemoryData,
        document_id: uuid.UUID,
    ) -> NoticeMemory:
        """Create a new NoticeMemory row and resolve supersession with existing notices.

        Args:
            session: Async database session
            memory_data: Structured metadata extracted from document
            document_id: UUID of the parent document in documents table

        Returns:
            The newly created and persisted NoticeMemory instance.
        """
        effective_d = cls._parse_date(memory_data.effective_date)
        expiry_d = cls._parse_date(memory_data.expiry_date)

        # Check for existing latest notice memory records with the same fingerprint
        query = select(NoticeMemory).where(
            NoticeMemory.content_fingerprint == memory_data.content_fingerprint,
            NoticeMemory.is_latest == True,  # noqa: E712
            NoticeMemory.document_id != document_id,
        )
        result = await session.execute(query)
        existing_matches = list(result.scalars().all())

        # Guard: Generic fingerprints (e.g. without specific topic) must NOT supersede dissimilar notices
        filtered_matches: list[NoticeMemory] = []
        for match in existing_matches:
            m_fp = memory_data.content_fingerprint
            if ":all:all:" in m_fp or m_fp.endswith(":all:all:current"):
                import re

                old_words = set(re.findall(r"\b\w{4,}\b", match.title_summary.lower()))
                new_words = set(re.findall(r"\b\w{4,}\b", memory_data.title_summary.lower()))
                if not old_words.intersection(new_words):
                    logger.info(
                        f"Skipping false supersession between dissimilar notices with generic fingerprint: "
                        f"'{match.title_summary}' vs '{memory_data.title_summary}'"
                    )
                    continue
            filtered_matches.append(match)
        existing_matches = filtered_matches

        # Check for Corrigendum / Revision triggers in title
        if cls.is_corrigendum_or_revision(memory_data.title_summary):
            import re

            ignore_words = {
                "notice",
                "order",
                "circular",
                "revised",
                "corrigendum",
                "college",
                "ajmer",
                "engineering",
                "schedule",
                "regarding",
                "date",
                "time",
                "table",
            }
            topic_words = {
                w
                for w in re.findall(r"\b[a-zA-Z]{4,}\b", memory_data.title_summary.lower())
                if w not in ignore_words
            }
            if topic_words and memory_data.department:
                dept_stmt = select(NoticeMemory).where(
                    NoticeMemory.department.ilike(memory_data.department),
                    NoticeMemory.is_latest == True,  # noqa: E712
                    NoticeMemory.document_id != document_id,
                )
                dept_candidates = list((await session.execute(dept_stmt)).scalars().all())
                for cand in dept_candidates:
                    if cand in existing_matches:
                        continue
                    cand_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", cand.title_summary.lower()))
                    if topic_words.intersection(cand_words):
                        logger.info(
                            f"Corrigendum/revision detected: '{memory_data.title_summary}' "
                            f"supersedes earlier matching notice '{cand.title_summary}' (id={cand.id})"
                        )
                        existing_matches.append(cand)

        # Check if already exists for this exact document (e.g. re-ingestion of updated doc)
        existing_doc_query = select(NoticeMemory).where(NoticeMemory.document_id == document_id)
        existing_self = (await session.execute(existing_doc_query)).scalar_one_or_none()

        new_is_latest = True
        superseded_by_id = None
        supersession_reason = None
        to_supersede: list[NoticeMemory] = []

        new_memory_id = existing_self.id if existing_self else uuid.uuid4()

        for old in existing_matches:
            # Determine which is newer
            # Rule 1: Compare effective_date if both have one
            # Rule 2: If dates absent or equal, the incoming document is considered newer
            old_is_newer = False
            if effective_d and old.effective_date:
                if effective_d < old.effective_date:
                    old_is_newer = True

            if old_is_newer:
                # The incoming document is actually an older notice uploaded out of order
                new_is_latest = False
                superseded_by_id = old.id
                supersession_reason = (
                    f"Uploaded version is older than active notice ({old.title_summary})"
                )
                logger.info(
                    f"Notice {new_memory_id} ({memory_data.title_summary}) marked superseded by existing {old.id}"
                )
            else:
                to_supersede.append(old)

        if not new_is_latest:
            to_supersede = []

        # Resolve ground truth from document if notice_memory fields are missing
        resolved_dept = memory_data.department
        resolved_sno = memory_data.notice_serial
        resolved_date = effective_d

        if (not resolved_dept or not resolved_sno or not resolved_date) and document_id:
            try:
                doc_stmt = (
                    select(Document, Department.name)
                    .outerjoin(Department, Document.department_id == Department.id)
                    .where(Document.id == document_id)
                )
                exec_res = await session.execute(doc_stmt)
                if hasattr(exec_res, "first"):
                    doc_res = exec_res.first()
                    if doc_res:
                        doc_obj, dept_name = doc_res
                        if not resolved_dept:
                            resolved_dept = dept_name
                        if not resolved_sno:
                            resolved_sno = doc_obj.notice_sno
                        if not resolved_date:
                            resolved_date = doc_obj.notice_date
            except (Exception, StopAsyncIteration):
                pass

        if existing_self:
            # Update existing row for this document
            existing_self.notice_type = memory_data.notice_type
            existing_self.department = resolved_dept
            existing_self.target_year = memory_data.target_year
            existing_self.target_semester = memory_data.target_semester
            existing_self.target_branch = memory_data.target_branch
            existing_self.academic_session = memory_data.academic_session
            existing_self.effective_date = resolved_date
            existing_self.expiry_date = expiry_d
            existing_self.notice_serial = resolved_sno
            existing_self.title_summary = memory_data.title_summary
            existing_self.key_facts = memory_data.key_facts
            existing_self.content_fingerprint = memory_data.content_fingerprint
            existing_self.is_latest = new_is_latest
            existing_self.superseded_by = superseded_by_id
            existing_self.supersession_reason = supersession_reason
            existing_self.raw_llm_response = memory_data.raw_llm_response
            record = existing_self
        else:
            record = NoticeMemory(
                id=new_memory_id,
                document_id=document_id,
                notice_type=memory_data.notice_type,
                department=resolved_dept,
                target_year=memory_data.target_year,
                target_semester=memory_data.target_semester,
                target_branch=memory_data.target_branch,
                academic_session=memory_data.academic_session,
                effective_date=resolved_date,
                expiry_date=expiry_d,
                notice_serial=resolved_sno,
                title_summary=memory_data.title_summary,
                key_facts=memory_data.key_facts,
                content_fingerprint=memory_data.content_fingerprint,
                is_latest=new_is_latest,
                superseded_by=superseded_by_id,
                supersession_reason=supersession_reason,
                raw_llm_response=memory_data.raw_llm_response,
            )
            session.add(record)

        # 1. Flush record FIRST so its ID definitely exists in notice_memory table
        await session.flush()

        # 2. Update older records to point to record.id (which is guaranteed to exist)
        if to_supersede and new_is_latest:
            for old in to_supersede:
                old.is_latest = False
                old.superseded_by = record.id
                old.supersession_reason = (
                    f"Superseded by newer notice ({memory_data.title_summary}) "
                    f"effective {memory_data.effective_date or 'today'}"
                )
                logger.info(
                    f"Superseded old notice memory {old.id} with new notice memory {record.id}"
                )
            await session.flush()

        return record
