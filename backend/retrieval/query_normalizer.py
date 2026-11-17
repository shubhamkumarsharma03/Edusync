"""Domain-Specific College NLP Query Normalizer for EduSync.

Pre-processes, cleans, and expands casual, abbreviated, and shorthand student queries
into high-recall semantic representations for both dense vector search and keyword FTS.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NormalizedQuery:
    """Encapsulates the original student query and its NLP-enriched variations."""

    original: str
    expanded_vector: str
    expanded_keyword: str
    detected_departments: list[str] = field(default_factory=list)
    detected_semesters: list[str] = field(default_factory=list)
    detected_categories: list[str] = field(default_factory=list)


class CollegeQueryNormalizer:
    """Regex and rule-based NLP query normalizer for institutional engineering college documents."""

    # 1. Core Institutional Shorthand / Acronym Mapping
    ACRONYM_MAP: list[tuple[re.Pattern[str], str]] = [
        # Timetable & Schedule terms
        (
            re.compile(
                r"\b(tt|t\.t\.|t\.t|time[- ]?table|timetables?|sched|schedule|classes|timing|timings)\b",
                re.IGNORECASE,
            ),
            "time table timetable schedule",
        ),
        # Degree programs
        (
            re.compile(r"\b(mtech|m\.tech|m[\s\.]*tech)\b", re.IGNORECASE),
            "M.Tech MTech Master of Technology",
        ),
        (
            re.compile(r"\b(btech|b\.tech|b[\s\.]*tech)\b", re.IGNORECASE),
            "B.Tech BTech Bachelor of Technology",
        ),
        (re.compile(r"\b(mca)\b", re.IGNORECASE), "MCA Computer Applications"),
        (re.compile(r"\b(mba)\b", re.IGNORECASE), "MBA Management Studies"),
        # Branch & Department terms
        (
            re.compile(
                r"\b(i\.t\.|information\s+technology|b\.?tech\s+it|it\s+dept|it\s+branch)\b|\bIT\b"
            ),
            "Information Technology IT",
        ),
        (
            re.compile(r"\b(cse|cs-it|cs)\b", re.IGNORECASE),
            "Computer Science and Engineering Computer Engineering",
        ),
        (
            re.compile(r"\b(cyber|csec|cyber[\s-]*security)\b", re.IGNORECASE),
            "Cyber Security CSE Cyber",
        ),
        (
            re.compile(r"\b(ca|sec[\s-]*ca|section[\s-]*ca)\b", re.IGNORECASE),
            "Section CA Computer Engineering",
        ),
        (
            re.compile(r"\b(cb|sec[\s-]*cb|section[\s-]*cb)\b", re.IGNORECASE),
            "Section CB Computer Engineering",
        ),
        (
            re.compile(r"\b(ce|civil)\b", re.IGNORECASE),
            "Civil Engineering",
        ),
        (
            re.compile(r"\b(ee|electrical)\b", re.IGNORECASE),
            "Electrical Engineering",
        ),
        (
            re.compile(r"\b(ece|electronics)\b", re.IGNORECASE),
            "Electronics and Communication Engineering",
        ),
        (
            re.compile(r"\b(mech|mechanical|b\.?tech\s+me|me\s+dept|me\s+branch)\b|\bME\b"),
            "Mechanical Engineering",
        ),
        (
            re.compile(r"\b(eic)\b", re.IGNORECASE),
            "Electronic Instrumentation and Control Engineering",
        ),
        # Semesters
        (re.compile(r"\b1st(\s*sem)?\b", re.IGNORECASE), "1st Sem 1st Semester"),
        (re.compile(r"\b2nd(\s*sem)?\b", re.IGNORECASE), "2nd Sem 2nd Semester"),
        (re.compile(r"\b3rd(\s*sem)?\b", re.IGNORECASE), "3rd Sem 3rd Semester"),
        (re.compile(r"\b4th(\s*sem)?\b", re.IGNORECASE), "4th Sem 4th Semester"),
        (re.compile(r"\b5th(\s*sem)?\b", re.IGNORECASE), "5th Sem 5th Semester"),
        (re.compile(r"\b6th(\s*sem)?\b", re.IGNORECASE), "6th Sem 6th Semester"),
        (re.compile(r"\b7th(\s*sem)?\b", re.IGNORECASE), "7th Sem 7th Semester"),
        (re.compile(r"\b8th(\s*sem)?\b", re.IGNORECASE), "8th Sem 8th Semester"),
        (re.compile(r"\bsem(ester)?s?\b", re.IGNORECASE), "semester sem"),
        # Common Subjects & Course Codes
        (
            re.compile(r"\bdsa\b", re.IGNORECASE),
            "DSA Data Structures and Algorithms",
        ),
        (
            re.compile(r"\boops?\b", re.IGNORECASE),
            "OOPS Object Oriented Programming",
        ),
        (
            re.compile(r"\b(digital\s+electronics)\b|\bDE\b"),
            "Digital Electronics DE",
        ),
        (
            re.compile(r"\bcn\b", re.IGNORECASE),
            "Computer Networks CN",
        ),
        (
            re.compile(r"\bse\b", re.IGNORECASE),
            "Software Engineering SE",
        ),
        (
            re.compile(r"\bml\b", re.IGNORECASE),
            "Machine Learning ML",
        ),
        (
            re.compile(r"\bos\b", re.IGNORECASE),
            "Operating Systems OS",
        ),
        (
            re.compile(r"\baem\b", re.IGNORECASE),
            "Advance Engineering Mathematics AEM",
        ),
        (
            re.compile(r"\bcoa\b", re.IGNORECASE),
            "Computer Organization and Architecture COA",
        ),
        (
            re.compile(r"\b(mfcs|mfos)\b", re.IGNORECASE),
            "Mathematical Foundations of Computer Science MFCS MFOS",
        ),
        (
            re.compile(r"\badbms\b", re.IGNORECASE),
            "Advanced Database Management Systems ADBMS",
        ),
        (
            re.compile(r"\bccdt\b", re.IGNORECASE),
            "Cloud Computing and Distributed Technologies CCDT",
        ),
        # Rooms and Labs
        (re.compile(r"\bs[\s-]*9\b", re.IGNORECASE), "Room S-9 S9"),
        (re.compile(r"\bs[\s-]*2\b", re.IGNORECASE), "Room S-2 S2"),
        (re.compile(r"\bs[\s-]*13\b", re.IGNORECASE), "Room S-13 S13"),
        (re.compile(r"\bnb[\s-]*111\b", re.IGNORECASE), "Room NB-111 NB111"),
        (re.compile(r"\bnb[\s-]*211\b", re.IGNORECASE), "Room NB-211 NB211"),
        (re.compile(r"\bg[\s-]*29\b", re.IGNORECASE), "Room G-29 G29"),
        (re.compile(r"\blab[\s-]*b\b", re.IGNORECASE), "Lab-B Lab B"),
        (re.compile(r"\blab[\s-]*a\b", re.IGNORECASE), "Lab-A Lab A"),
        (re.compile(r"\blab[\s-]*d\b", re.IGNORECASE), "Lab-D Lab D"),
        # Faculty & Roles
        (
            re.compile(r"\b(dkk|deepak\s+kazi)\b", re.IGNORECASE),
            "Dr. Deepak Kumar Kazi DKK OOPS",
        ),
        (
            re.compile(r"\b(sw|shalini\s+walia)\b", re.IGNORECASE),
            "Mrs. Shalini Walia SW AEM",
        ),
        (
            re.compile(r"\b(prof(essor)?|dr|sir|ma'?am|faculty|teacher)\b", re.IGNORECASE),
            "faculty instructor teacher",
        ),
        # Scholarships, Financial Aid & Government Schemes
        (
            re.compile(
                r"\b(scholarships?|scooty|yojana|yojna|fellowship|financial[\s-]*aid)\b",
                re.IGNORECASE,
            ),
            "scholarship scheme yojana distribution",
        ),
        (
            re.compile(r"\b(kalpana|kalpana[\s-]*chawla)\b", re.IGNORECASE),
            "Kalpana Chawla scooty scheme",
        ),
    ]

    # Entity detection keywords
    SEMESTER_DETECTION = {
        "1st": ["1st", "first", "1 sem", "1st sem"],
        "2nd": ["2nd", "second", "2 sem", "2nd sem"],
        "3rd": ["3rd", "third", "3 sem", "3rd sem"],
        "4th": ["4th", "fourth", "4 sem", "4th sem"],
        "5th": ["5th", "fifth", "5 sem", "5th sem"],
        "6th": ["6th", "sixth", "6 sem", "6th sem"],
        "7th": ["7th", "seventh", "7 sem", "7th sem"],
        "8th": ["8th", "eighth", "8 sem", "8th sem"],
    }

    DEPARTMENT_DETECTION = {
        "Computer Science and Engineering": ["cse", "cs", "computer", "ca", "cb"],
        "Information Technology": ["information technology", "info tech", "btech it", "it dept"],
        "Cyber Security": ["cyber", "cyber security"],
        "Examination Section": ["examination section", "exam cell", "exam branch"],
        "Registrar Section": ["registrar", "office order", "admin"],
        "Academic Section": ["academic", "admission"],
        "Proctor Section": ["proctor", "discipline", "id card", "anti-ragging"],
        "Mechanical Engineering": ["mech", "mechanical", "btech me", "me dept"],
        "Electrical Engineering": ["ee", "electrical"],
        "Civil Engineering": ["ce", "civil"],
        "Electronics & Communication Engineering": ["ece", "electronics"],
    }

    @classmethod
    def normalize(cls, query: str) -> NormalizedQuery:
        """Transform user query into enriched search representations and extract entities."""
        raw = query.strip()
        if not raw:
            return NormalizedQuery(
                original="",
                expanded_vector="",
                expanded_keyword="",
            )

        # 1. Extract Named Entities
        lower_raw = raw.lower()
        detected_semesters = []
        for sem, triggers in cls.SEMESTER_DETECTION.items():
            if any(re.search(rf"\b{re.escape(tr)}\b", lower_raw) for tr in triggers):
                detected_semesters.append(sem)

        detected_departments = []
        for dept, triggers in cls.DEPARTMENT_DETECTION.items():
            if any(re.search(rf"\b{re.escape(tr)}\b", lower_raw) for tr in triggers):
                detected_departments.append(dept)

        # 2. Build Expanded Vector Query (Dense representation)
        expanded_v = raw
        for pattern, replacement in cls.ACRONYM_MAP:
            expanded_v = pattern.sub(replacement, expanded_v)

        # Clean redundant whitespace
        expanded_v = " ".join(expanded_v.split())

        # 3. Build Keyword Search Representation (FTS-friendly)
        kw_clean = raw
        kw_clean = re.sub(r"\bmtech\b", "M.Tech", kw_clean, flags=re.IGNORECASE)
        kw_clean = re.sub(r"\bbtech\b", "B.Tech", kw_clean, flags=re.IGNORECASE)
        kw_clean = re.sub(r"\btt\b", "timetable", kw_clean, flags=re.IGNORECASE)
        kw_clean = re.sub(
            r"\b(i\.t\.|information technology)\b|\bIT\b", "Information Technology", kw_clean
        )
        kw_clean = re.sub(r"\bsem\b", "Semester", kw_clean, flags=re.IGNORECASE)
        kw_clean = re.sub(r"\bca\b", "CA", kw_clean, flags=re.IGNORECASE)
        kw_clean = re.sub(r"\bcb\b", "CB", kw_clean, flags=re.IGNORECASE)
        kw_clean = re.sub(r"\bcyber\b", "Cyber", kw_clean, flags=re.IGNORECASE)
        kw_clean = re.sub(r"\bcse\b", "Computer Engineering", kw_clean, flags=re.IGNORECASE)
        expanded_k = " ".join(kw_clean.split())

        logger.debug(
            f"Query normalized: original='{raw}' -> vector='{expanded_v}' | keyword='{expanded_k}'"
        )

        return NormalizedQuery(
            original=raw,
            expanded_vector=expanded_v,
            expanded_keyword=expanded_k,
            detected_departments=detected_departments,
            detected_semesters=detected_semesters,
        )


# Global singleton instance
query_normalizer = CollegeQueryNormalizer()
