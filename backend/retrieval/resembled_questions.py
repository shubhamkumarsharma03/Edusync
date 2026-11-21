import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Verified Question Bank grounded in Engineering College Ajmer circulars & notices
INSTITUTIONAL_QUESTION_BANK = [
    # Examination & Schedules
    {
        "keywords": ["exam", "midterm", "schedule", "timetable", "date", "when", "test", "time"],
        "questions": [
            "Mid-term exam schedule for CSE",
            "Semester fee notice and due dates",
            "Mercy exam rules for B.Tech",
            "Central Library book issue timings",
        ],
    },
    {
        "keywords": [
            "mercy",
            "back",
            "re-evaluation",
            "fail",
            "marks",
            "result",
            "copy",
            "inspection",
        ],
        "questions": [
            "Mercy exam rules for B.Tech",
            "Back exam and re-evaluation guidelines",
            "Copy inspection and answer booklet viewing rules",
            "Main semester examination form deadlines",
        ],
    },
    # Fees, Challan & Scholarships
    {
        "keywords": [
            "fee",
            "pay",
            "money",
            "cost",
            "challan",
            "dues",
            "scholarship",
            "concession",
            "refund",
        ],
        "questions": [
            "Semester fee notice and due dates",
            "Online fee payment and bank challan deposit process",
            "Post-matric scholarship and fee concession rules",
            "Hostel admission and mess fee schedule",
        ],
    },
    # Syllabus, Attendance & Academics
    {
        "keywords": [
            "syllabus",
            "scheme",
            "curriculum",
            "subject",
            "attendance",
            "75",
            "classes",
            "calendar",
        ],
        "questions": [
            "B.Tech scheme and syllabus for all branches",
            "Minimum 75% attendance rule for semester exams",
            "Academic calendar and semester commencement dates",
            "Central Library book issue timings",
        ],
    },
    # Library, Books & Facilities
    {
        "keywords": ["library", "book", "issue", "borrow", "return", "timings", "reading", "room"],
        "questions": [
            "Central Library book issue timings",
            "Book bank facility rules for students",
            "Academic calendar and semester commencement dates",
            "Official college working hours and office timings",
        ],
    },
    # Certificates, Office, Hostel & Grievances
    {
        "keywords": [
            "certificate",
            "bonafide",
            "character",
            "hostel",
            "room",
            "mess",
            "office",
            "contact",
            "grievance",
            "ragging",
        ],
        "questions": [
            "Bonafide and character certificate application process",
            "Hostel allotment and clearance procedure",
            "Anti-ragging committee and student grievance mechanism",
            "Official college administration office timings and contacts",
        ],
    },
    # Masters (MCA / MBA)
    {
        "keywords": ["mca", "mba", "master", "postgraduate", "pg"],
        "questions": [
            "MCA midterm examination timetable and syllabus",
            "MBA semester fee notice and due dates",
            "Master degree project dissertation guidelines",
            "Central Library book issue timings",
        ],
    },
]

DEFAULT_SUGGESTIONS = [
    "Mid-term exam schedule for CSE",
    "Semester fee notice and due dates",
    "Mercy exam rules for B.Tech",
    "Central Library book issue timings",
]


async def get_closely_resembled_questions(
    query: str,
    department: str | None = None,
    retrieved_chunks: list[Any] | None = None,
) -> list[str]:
    """Analyze query and context to return closely resembled questions EduSync can answer.

    Args:
        query: Raw or rewritten student query that was unanswerable or low confidence.
        department: Optional department scope.
        retrieved_chunks: Retrieved candidate chunks from hybrid search.

    Returns:
        List of 3 to 4 distinct, highly relevant questions grounded in official circulars.
    """
    clean_q = query.lower()
    tokens = set(re.findall(r"\w+", clean_q))

    candidates: list[tuple[float, str]] = []

    # 1. Match against domain-curated question bank
    for category in INSTITUTIONAL_QUESTION_BANK:
        overlap = len(tokens.intersection(category["keywords"]))
        if overlap > 0:
            for q in category["questions"]:
                score = float(overlap)
                # Boost if department matches
                if department and department.lower() in q.lower():
                    score += 2.0
                candidates.append((score, q))

    # 2. Extract potential questions from retrieved chunk headlines if available
    if retrieved_chunks:
        for chunk in retrieved_chunks[:3]:
            content = (
                getattr(chunk, "content", "")
                if not isinstance(chunk, dict)
                else chunk.get("content", "")
            )
            if content:
                first_line = content.split("\n")[0].strip("# ").strip()
                if 10 < len(first_line) < 70 and not first_line.startswith("http"):
                    formatted_q = f"Notice: {first_line}"
                    candidates.append((1.5, formatted_q))

    # 3. Department specific recommendations if provided
    if department:
        clean_dept = department.strip()
        dept_q = f"Mid-term exam schedule for {clean_dept}"
        dept_s = f"{clean_dept} syllabus and course scheme"
        candidates.append((2.5, dept_q))
        candidates.append((2.0, dept_s))

    # Deduplicate while preserving highest score order
    candidates.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    result: list[str] = []

    for _, q in candidates:
        if q not in seen and q.lower() != clean_q:
            seen.add(q)
            result.append(q)
            if len(result) >= 4:
                break

    # If fewer than 3 found, backfill from DEFAULT_SUGGESTIONS
    if len(result) < 3:
        for default_q in DEFAULT_SUGGESTIONS:
            if default_q not in seen:
                seen.add(default_q)
                result.append(default_q)
                if len(result) >= 3:
                    break

    return result[:4]
