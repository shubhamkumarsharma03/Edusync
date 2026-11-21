"""NoticeAnalyzer — Single-call Gemini structured extraction for institutional notices.

Analyzes document content and extracts:
- notice_type, department, target_year, target_semester, target_branch
- academic_session, effective_date, expiry_date, notice_serial
- title_summary, key_facts, content_fingerprint, supersedes_description

Uses exactly 1 Gemini API call per notice with response_mime_type="application/json".
"""

import asyncio
import json
import logging
import re

from api.config import get_settings
from ingestion.schemas import FetchedDocument, NoticeMemoryData

logger = logging.getLogger(__name__)

# Fixed branch enum for deterministic fingerprints and scoped retrieval
ALLOWED_BRANCHES = {"CSE", "IT", "ECE", "EE", "ME", "CE", "AUTO"}

# Branch alias mapping for normalization
BRANCH_ALIASES = {
    "COMPUTER SCIENCE": "CSE",
    "COMPUTER SCIENCE AND ENGINEERING": "CSE",
    "INFORMATION TECHNOLOGY": "IT",
    "ELECTRONICS AND COMMUNICATION": "ECE",
    "ELECTRONICS & COMMUNICATION": "ECE",
    "ELECTRICAL ENGINEERING": "EE",
    "ELECTRICAL": "EE",
    "MECHANICAL ENGINEERING": "ME",
    "MECHANICAL": "ME",
    "CIVIL ENGINEERING": "CE",
    "CIVIL": "CE",
    "AUTOMOBILE ENGINEERING": "AUTO",
    "AUTOMOBILE": "AUTO",
}

ANALYSIS_PROMPT = """
You are an expert document analyst for an Engineering College (institutional notices, circulars, exam schedules, timetables, fee notices).
Analyze this institutional notice/document and extract ALL of the requested fields in a single JSON response.

DOCUMENT TEXT:
---
{document_text}
---

Return a single JSON object with EXACTLY these fields:
{{
  "notice_type": "<one of: timetable, exam_schedule, fee_notice, circular, syllabus, office_order, result, admission, scholarship, hostel, other>",
  "department": "<department name like Computer Science, Mechanical, Administration, or null if campus-wide/all>",
  "target_year": ["<1st Year|2nd Year|3rd Year|4th Year>"] or null if applies to all years,
  "target_semester": ["<1st Sem|2nd Sem|3rd Sem|4th Sem|5th Sem|6th Sem|7th Sem|8th Sem>"] or null if applies to all semesters,
  "target_branch": ["<CSE|IT|ECE|EE|ME|CE|AUTO>"] or null if applies to all branches,
  "academic_session": "<e.g. 2025-26, 2026-27>" or null,
  "effective_date": "<YYYY-MM-DD>" or null,
  "expiry_date": "<YYYY-MM-DD>" or null,
  "notice_serial": "<official reference/serial number, e.g. ECA/COE/2026/041>" or null,
  "title_summary": "<concise 1-line title describing this notice>",
  "key_facts": [
    {{"fact": "<specific fact like date, amount, venue, or deadline>", "category": "<date|amount|deadline|rule|schedule>"}}
  ],
  "content_fingerprint": "<canonical lowercase slug: notice_type:branch:semester:topic:session, e.g. timetable:cse:3rd-sem:mid-sem:2025-26>",
  "supersedes_description": "<if this notice explicitly revises, amends, or replaces an earlier notice or schedule, state what it replaces; otherwise null>"
}}

Rules:
1. target_branch MUST only use codes from: CSE, IT, ECE, EE, ME, CE, AUTO. If all branches apply, use null.
2. Dates must be in YYYY-MM-DD format if known.
3. key_facts must capture every important date, fee amount, deadline, room number, or condition mentioned.
4. content_fingerprint must be deterministic: identical subject/event = identical fingerprint so supersessions can be detected.
5. Be accurate and faithful to the text; do not hallucinate dates or numbers.
6. Institutional notices are often bilingual (Hindi and English). Interpret Hindi Devanagari text accurately (e.g. कार्यालय आदेश = office_order, प्रवेश निरस्त / प्रवेश = admission, समय सारिणी = timetable, शुल्क = fee_notice, क्रमांक/पत्रांक = notice_serial).
"""


class NoticeAnalyzer:
    """Extracts structured notice metadata in exactly 1 Gemini API call."""

    @classmethod
    def _normalize_branches(cls, branches: list[str] | None) -> list[str] | None:
        """Normalize extracted branch names against the fixed enum."""
        if not branches:
            return None
        normalized = set()
        for b in branches:
            b_upper = b.strip().upper()
            if b_upper in ALLOWED_BRANCHES:
                normalized.add(b_upper)
            elif b_upper in BRANCH_ALIASES:
                normalized.add(BRANCH_ALIASES[b_upper])
            else:
                for alias, code in BRANCH_ALIASES.items():
                    if alias in b_upper:
                        normalized.add(code)
                        break
        return sorted(normalized) if normalized else None

    @classmethod
    def _canonical_fingerprint(
        cls,
        notice_type: str,
        branches: list[str] | None,
        semesters: list[str] | None,
        session: str | None,
        raw_slug: str | None = None,
        topic: str | None = None,
    ) -> str:
        """Ensure the fingerprint is deterministic and lowercase."""
        if raw_slug and ":" in raw_slug:
            # Clean raw slug to safe lowercase characters
            cleaned = re.sub(r"[^a-z0-9:\-_]", "", raw_slug.lower().strip())
            if len(cleaned) > 5:
                return cleaned

        branch_part = "-".join(sorted(branches)) if branches else "all"
        sem_part = (
            "-".join(sorted(re.sub(r"[^0-9a-z]", "", s.lower()) for s in semesters))
            if semesters
            else "all"
        )
        session_part = re.sub(r"[^0-9\-]", "", session) if session else "current"
        type_part = re.sub(r"[^a-z0-9]", "", notice_type.lower()) or "general"
        topic_part = re.sub(r"[^a-z0-9]", "", (topic or "").lower())[:30]
        if topic_part:
            return f"{type_part}:{branch_part.lower()}:{sem_part}:{topic_part}:{session_part}"
        return f"{type_part}:{branch_part.lower()}:{sem_part}:{session_part}"

    @classmethod
    def _fallback_extract(
        cls, text: str, url: str, metadata: dict | None = None
    ) -> NoticeMemoryData:
        """Rule-based heuristic fallback if Gemini API is unavailable."""
        meta = metadata or {}
        dept_val = meta.get("department") or meta.get("source_section")
        serial_val = meta.get("sno") or meta.get("notice_sno")
        date_val = meta.get("notice_date") or meta.get("date")

        lower_text = text.lower()
        notice_type = "other"
        for kw, ntype in [
            ("time table", "timetable"),
            ("timetable", "timetable"),
            ("exam", "exam_schedule"),
            ("fee", "fee_notice"),
            ("circular", "circular"),
            ("syllabus", "syllabus"),
            ("scholarship", "scholarship"),
            ("hostel", "hostel"),
        ]:
            if kw in lower_text or kw in url.lower():
                notice_type = ntype
                break

        # Detect branches
        branches = []
        for b in ALLOWED_BRANCHES:
            if re.search(r"\b" + b + r"\b", text, re.IGNORECASE):
                branches.append(b)

        # Detect semesters
        sems = []
        for s in range(1, 9):
            if re.search(rf"\b{s}(st|nd|rd|th)?\s*(sem|semester)\b", lower_text):
                suffix = "st" if s == 1 else "nd" if s == 2 else "rd" if s == 3 else "th"
                sems.append(f"{s}{suffix} Sem")

        # Extract title from metadata or leading lines, skipping generic college header
        title = meta.get("title") or "Institutional Notice"
        if title == "Institutional Notice":
            for line in text.strip().split("\n"):
                clean_l = line.strip().strip("#* ").strip()
                if not clean_l:
                    continue
                if re.search(
                    r"^(government\s+)?engineering\s+college(\s+ajmer)?$", clean_l, re.IGNORECASE
                ):
                    continue
                if re.search(r"^department\s+of", clean_l, re.IGNORECASE):
                    continue
                title = clean_l[:120]
                break

        fingerprint = cls._canonical_fingerprint(
            notice_type=notice_type,
            branches=branches if branches else None,
            semesters=sems if sems else None,
            session=None,
            topic=title,
        )

        return NoticeMemoryData(
            notice_type=notice_type,
            department=dept_val,
            target_year=None,
            target_semester=sems or None,
            target_branch=branches or None,
            academic_session=None,
            effective_date=date_val,
            expiry_date=None,
            notice_serial=serial_val,
            title_summary=title,
            key_facts=[],
            content_fingerprint=fingerprint,
            supersedes_description=None,
            raw_llm_response={"fallback": True},
        )

    @classmethod
    async def analyze(cls, fetched: FetchedDocument) -> NoticeMemoryData:
        """Perform exactly 1 Gemini API call to extract structured notice metadata.

        Falls back gracefully to heuristic extraction if Gemini is unconfigured or fails.
        """
        settings = get_settings()
        api_key = settings.GEMINI_API_KEY

        # Check if valid key exists
        if not api_key or api_key in ("your-gemini-api-key", "placeholder", ""):
            logger.info("Gemini API key not configured. Using rule-based metadata fallback.")
            return cls._fallback_extract(
                fetched.extracted_text, fetched.source_url, metadata=fetched.metadata
            )

        # Assemble document text including tables
        doc_parts = [fetched.extracted_text]
        for tbl in fetched.tables:
            tbl_md = tbl.to_markdown()
            if tbl_md:
                doc_parts.append(tbl_md)

        full_text = "\n\n".join(doc_parts)
        # Truncate to first ~24,000 characters (~6000 tokens)
        truncated_text = full_text[:24000]

        prompt = ANALYSIS_PROMPT.format(document_text=truncated_text)

        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            model_name = getattr(settings, "GEMINI_ANALYSIS_MODEL", "gemini-2.5-flash")

            def _call_gemini() -> str:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "max_output_tokens": 1500,
                    },
                )
                return response.text or "{}"

            response_text = await asyncio.to_thread(_call_gemini)
            raw_json = json.loads(response_text)

            # Normalize branches to fixed enum
            raw_branches = raw_json.get("target_branch")
            normalized_branches = cls._normalize_branches(raw_branches)

            notice_type = str(raw_json.get("notice_type") or "other").lower().strip()
            title_summary = str(raw_json.get("title_summary") or "").strip()
            if not title_summary:
                title_summary = fetched.extracted_text.strip().split("\n")[0][:120]

            fingerprint = cls._canonical_fingerprint(
                notice_type=notice_type,
                branches=normalized_branches,
                semesters=raw_json.get("target_semester"),
                session=raw_json.get("academic_session"),
                raw_slug=raw_json.get("content_fingerprint"),
            )

            # Ensure key_facts is a list of dicts
            key_facts = raw_json.get("key_facts") or []
            if not isinstance(key_facts, list):
                key_facts = []

            dept_val = (
                raw_json.get("department")
                or fetched.metadata.get("department")
                or fetched.metadata.get("source_section")
            )
            eff_date = (
                raw_json.get("effective_date")
                or fetched.metadata.get("notice_date")
                or fetched.metadata.get("date")
            )
            serial_val = (
                raw_json.get("notice_serial")
                or fetched.metadata.get("sno")
                or fetched.metadata.get("notice_sno")
            )

            return NoticeMemoryData(
                notice_type=notice_type,
                department=dept_val,
                target_year=raw_json.get("target_year"),
                target_semester=raw_json.get("target_semester"),
                target_branch=normalized_branches,
                academic_session=raw_json.get("academic_session"),
                effective_date=eff_date,
                expiry_date=raw_json.get("expiry_date"),
                notice_serial=serial_val,
                title_summary=title_summary,
                key_facts=key_facts,
                content_fingerprint=fingerprint,
                supersedes_description=raw_json.get("supersedes_description"),
                raw_llm_response=raw_json,
            )

        except Exception as e:
            logger.error(
                f"Gemini notice analysis failed: {e}. Falling back to heuristic extraction."
            )
            return cls._fallback_extract(
                fetched.extracted_text, fetched.source_url, metadata=fetched.metadata
            )
