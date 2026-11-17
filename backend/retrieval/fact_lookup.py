"""FactLookup — Direct key_facts lookup from notice_memory for fast-path answering.

Allows instantaneous retrieval of verified dates, amounts, deadlines, and schedules
without needing to scan through chunk text.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.document import Document
from models.notice_memory import NoticeMemory
from retrieval.query_normalizer import query_normalizer

logger = logging.getLogger(__name__)


@dataclass
class FactResult:
    """A verified institutional fact retrieved directly from notice_memory."""

    fact: str
    category: str
    notice_title: str
    notice_type: str
    source_url: str
    last_verified: datetime | None
    effective_date: date | None
    document_id: str
    confidence: float = 1.0


class FactLookup:
    """Queries notice_memory key_facts for fast-path fact retrieval."""

    @classmethod
    async def search(
        cls,
        session: AsyncSession,
        query: str,
        limit: int = 5,
    ) -> list[FactResult]:
        """Search key_facts from active (is_latest=true) notice memory records.

        Matches against branch, semester, department, and fact keywords in the user query.
        """
        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return []

        norm = query_normalizer.normalize(query)
        detected_depts = norm.detected_departments or []

        # Detect branches from query

        query_branches: list[str] = []
        for b in ["CSE", "IT", "ECE", "EE", "ME", "CE", "AUTO"]:
            if re.search(r"\b" + b + r"\b", query, re.IGNORECASE):
                query_branches.append(b)

        # Detect semester from query
        query_semesters: list[str] = []
        for s in range(1, 9):
            if re.search(rf"\b{s}(st|nd|rd|th)?\s*(sem|semester)\b", cleaned_query):
                suffix = "st" if s == 1 else "nd" if s == 2 else "rd" if s == 3 else "th"
                query_semesters.append(f"{s}{suffix} Sem")

        # Query notice_memory joined with Document
        stmt = (
            select(
                NoticeMemory.key_facts,
                NoticeMemory.title_summary,
                NoticeMemory.notice_type,
                NoticeMemory.target_branch,
                NoticeMemory.target_semester,
                NoticeMemory.department,
                NoticeMemory.effective_date,
                NoticeMemory.document_id,
                Document.source_url,
                Document.last_checked_at.label("last_verified"),
            )
            .join(Document, NoticeMemory.document_id == Document.id)
            .where(
                NoticeMemory.is_latest == True,  # noqa: E712
                Document.status == "fresh",
            )
            .order_by(
                NoticeMemory.effective_date.desc().nullslast(), NoticeMemory.analyzed_at.desc()
            )
            .limit(25)
        )

        rows = (await session.execute(stmt)).all()
        if not rows:
            return []

        # Extract words from query for keyword scoring
        query_words = set(re.findall(r"\b\w{3,}\b", cleaned_query))

        results: list[FactResult] = []

        for row in rows:
            facts = row.key_facts
            if not isinstance(facts, list):
                continue

            # Branch match bonus
            branch_match = False
            if query_branches:
                doc_branches = row.target_branch or []
                if any(b in doc_branches for b in query_branches) or not doc_branches:
                    branch_match = True
            else:
                branch_match = True

            # Semester match bonus
            sem_match = False
            if query_semesters:
                doc_sems = row.target_semester or []
                if any(s in doc_sems for s in query_semesters) or not doc_sems:
                    sem_match = True
            else:
                sem_match = True

            # Department match bonus
            dept_match = False
            if detected_depts:
                doc_dept = row.department or ""
                if any(d.lower() in doc_dept.lower() for d in detected_depts):
                    dept_match = True
            else:
                dept_match = True

            for item in facts:
                if not isinstance(item, dict):
                    continue
                fact_text = item.get("fact", "")
                if not fact_text:
                    continue
                category = item.get("category", "general")

                fact_words = set(re.findall(r"\b\w{3,}\b", fact_text.lower()))
                overlap = query_words.intersection(fact_words)

                score = 0.0
                if overlap:
                    score += len(overlap) / max(len(query_words), 1)

                if branch_match and query_branches:
                    score += 0.3
                if sem_match and query_semesters:
                    score += 0.3
                if dept_match and detected_depts:
                    score += 0.2

                if score > 0.35 or (branch_match and sem_match and overlap):
                    results.append(
                        FactResult(
                            fact=fact_text,
                            category=category,
                            notice_title=row.title_summary,
                            notice_type=row.notice_type,
                            source_url=row.source_url,
                            last_verified=row.last_verified,
                            effective_date=row.effective_date,
                            document_id=str(row.document_id),
                            confidence=min(1.0, score),
                        )
                    )

        # Sort by confidence descending
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:limit]

    @classmethod
    def format_facts_context(cls, facts: list[FactResult]) -> str:
        """Format a list of facts into a Markdown block for prompt enrichment."""
        if not facts:
            return ""

        lines = ["### Verified Notice Facts (from latest active institutional notices):"]
        for f in facts:
            date_str = f" [Effective: {f.effective_date}]" if f.effective_date else ""
            lines.append(f"- **[{f.notice_title}]** ({f.category}): {f.fact}{date_str}")
        return "\n".join(lines)
