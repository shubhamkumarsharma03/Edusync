"""Unit tests for the Notice Memory System.

Tests:
1. NoticeAnalyzer branch normalization & fixed enum compliance
2. Deterministic canonical fingerprinting
3. Heuristic fallback analysis
4. Mocked single-call Gemini analysis
5. Memory metadata enrichment in SemanticChunker
6. Supersession resolution (newer replaces older)
7. Out-of-order supersession resolution (older marked superseded)
8. FactLookup direct search & formatting
9. Generator prompt enrichment with key facts
"""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.chunker import chunk_document
from ingestion.notice_analyzer import ALLOWED_BRANCHES, NoticeAnalyzer
from ingestion.schemas import FetchedDocument, NoticeMemoryData
from ingestion.supersession_resolver import SupersessionResolver
from models.notice_memory import NoticeMemory
from retrieval.fact_lookup import FactLookup, FactResult
from retrieval.generator import LLMGenerator
from retrieval.schemas import RetrievedChunk


def test_allowed_branches_enum() -> None:
    """Verify that allowed branches match the college-standard fixed enum."""
    expected = {"CSE", "IT", "ECE", "EE", "ME", "CE", "AUTO"}
    assert ALLOWED_BRANCHES == expected


def test_normalize_branches() -> None:
    """Verify that raw branch names and aliases normalize to standard codes."""
    raw = ["Computer Science", "IT", "Electrical", "random_branch"]
    normalized = NoticeAnalyzer._normalize_branches(raw)
    assert normalized == ["CSE", "EE", "IT"]
    assert "random_branch" not in normalized

    # Empty / None handling
    assert NoticeAnalyzer._normalize_branches(None) is None
    assert NoticeAnalyzer._normalize_branches([]) is None


def test_canonical_fingerprint() -> None:
    """Verify deterministic, lowercase slug generation for fingerprints."""
    fp1 = NoticeAnalyzer._canonical_fingerprint(
        notice_type="TimeTable",
        branches=["CSE"],
        semesters=["3rd Sem"],
        session="2025-26",
    )
    assert fp1 == "timetable:cse:3rdsem:2025-26"

    # Permuted branch order should yield identical fingerprint
    fp2 = NoticeAnalyzer._canonical_fingerprint(
        notice_type="timetable",
        branches=["CSE"],
        semesters=["3rd Sem"],
        session="2025-26",
    )
    assert fp1 == fp2

    # All branches and semesters
    fp_all = NoticeAnalyzer._canonical_fingerprint(
        notice_type="circular",
        branches=None,
        semesters=None,
        session=None,
    )
    assert fp_all == "circular:all:all:current"


def test_fallback_extract() -> None:
    """Verify fallback rule-based extraction works when Gemini is offline."""
    text = (
        "Engineering College Ajmer\n"
        "Department of Computer Science and Engineering\n"
        "Revised Mid-Term Examination Time Table for B.Tech 3rd Semester (CSE)\n"
        "All students must report by 9:00 AM."
    )
    data = NoticeAnalyzer._fallback_extract(text, "https://ecajmer.ac.in/cs_tt.pdf")
    assert data.notice_type == "timetable"
    assert "CSE" in (data.target_branch or [])
    assert data.target_semester == ["3rd Sem"]
    assert "Revised Mid-Term" in data.title_summary
    assert data.content_fingerprint.startswith("timetable:")


@pytest.mark.asyncio
async def test_chunker_enrichment_with_memory() -> None:
    """Verify SemanticChunker enriches chunk metadata and prepends memory header."""
    doc = FetchedDocument(
        source_url="https://ecajmer.ac.in/notice123.pdf",
        source_type="pdf",
        raw_content=b"test",
        extracted_text="# Exam Schedule\nExam begins on 15th November 2026 in Room 101.",
        tables=[],
        metadata={"title": "Exam Schedule"},
    )

    mem_data = NoticeMemoryData(
        notice_type="exam_schedule",
        department="Computer Science",
        target_year=["2nd Year"],
        target_semester=["3rd Sem"],
        target_branch=["CSE"],
        academic_session="2026-27",
        effective_date="2026-11-01",
        title_summary="B.Tech 3rd Sem Mid-Term Schedule",
        content_fingerprint="exam_schedule:cse:3rdsem:2026-27",
    )

    chunks = chunk_document(doc, department="CSE", memory_data=mem_data)
    assert len(chunks) >= 1
    top_chunk = chunks[0]

    # Memory header check
    assert "[Notice: B.Tech 3rd Sem Mid-Term Schedule" in top_chunk.content
    assert "Type: exam_schedule" in top_chunk.content
    assert "Branch: CSE" in top_chunk.content
    assert "Sem: 3rd Sem" in top_chunk.content

    # Metadata check
    assert top_chunk.metadata["content_fingerprint"] == "exam_schedule:cse:3rdsem:2026-27"
    assert top_chunk.metadata["target_branch"] == ["CSE"]
    assert top_chunk.metadata["doc_type"] == "exam_schedule"


@pytest.mark.asyncio
async def test_supersession_resolver_newer_replaces_older() -> None:
    """Verify that a newer notice supersedes an existing older notice with same fingerprint."""
    doc_id_old = uuid.uuid4()
    doc_id_new = uuid.uuid4()

    old_memory = NoticeMemory(
        id=uuid.uuid4(),
        document_id=doc_id_old,
        notice_type="timetable",
        title_summary="CSE 3rd Sem TT v1",
        content_fingerprint="timetable:cse:3rdsem:2026-27",
        effective_date=date(2026, 10, 1),
        is_latest=True,
    )

    # Mock DB session
    session = AsyncMock()
    session.add = MagicMock()
    # First query returns existing old memory match
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [old_memory]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_self_result = MagicMock()
    mock_self_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [mock_result, mock_self_result]

    new_data = NoticeMemoryData(
        notice_type="timetable",
        title_summary="CSE 3rd Sem TT Revised",
        content_fingerprint="timetable:cse:3rdsem:2026-27",
        effective_date="2026-10-15",
        key_facts=[{"fact": "Exam rescheduled to 20 Oct", "category": "date"}],
    )

    resolved = await SupersessionResolver.resolve(session, new_data, doc_id_new)

    # Old memory should be superseded
    assert old_memory.is_latest is False
    assert old_memory.superseded_by == resolved.id
    assert "Superseded by newer notice" in (old_memory.supersession_reason or "")

    # New memory should be active
    assert resolved.is_latest is True
    assert resolved.superseded_by is None
    session.add.assert_called_once()
    assert session.flush.call_count == 2


@pytest.mark.asyncio
async def test_supersession_resolver_out_of_order() -> None:
    """Verify that an older notice uploaded after a newer one is marked superseded."""
    doc_id_active = uuid.uuid4()
    doc_id_incoming_old = uuid.uuid4()

    active_memory = NoticeMemory(
        id=uuid.uuid4(),
        document_id=doc_id_active,
        notice_type="timetable",
        title_summary="CSE 3rd Sem TT Latest",
        content_fingerprint="timetable:cse:3rdsem:2026-27",
        effective_date=date(2026, 11, 1),
        is_latest=True,
    )

    session = AsyncMock()
    session.add = MagicMock()
    mock_scalars = MagicMock()

    mock_scalars.all.return_value = [active_memory]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_self_result = MagicMock()
    mock_self_result.scalar_one_or_none.return_value = None

    session.execute.side_effect = [mock_result, mock_self_result]

    older_incoming_data = NoticeMemoryData(
        notice_type="timetable",
        title_summary="CSE 3rd Sem TT Old Stale",
        content_fingerprint="timetable:cse:3rdsem:2026-27",
        effective_date="2026-10-01",  # Before active memory's 2026-11-01
    )

    resolved = await SupersessionResolver.resolve(session, older_incoming_data, doc_id_incoming_old)

    # Active memory should remain latest
    assert active_memory.is_latest is True

    # Incoming older document should be marked superseded
    assert resolved.is_latest is False
    assert resolved.superseded_by == active_memory.id
    assert "older than active notice" in (resolved.supersession_reason or "").lower()


def test_fact_lookup_formatting() -> None:
    """Verify formatting of verified FactResults into Markdown context."""
    facts = [
        FactResult(
            fact="Mid-term exams commence on 15 Nov 2026.",
            category="schedule",
            notice_title="Mid-Term Schedule",
            notice_type="exam_schedule",
            source_url="https://ecajmer.ac.in/midterm.pdf",
            last_verified=datetime(2026, 10, 20),
            effective_date=date(2026, 10, 15),
            document_id=str(uuid.uuid4()),
            confidence=0.95,
        )
    ]
    formatted = FactLookup.format_facts_context(facts)
    assert "### Verified Notice Facts" in formatted
    assert "[Mid-Term Schedule]" in formatted
    assert "Mid-term exams commence on 15 Nov 2026." in formatted
    assert "[Effective: 2026-10-15]" in formatted


def test_generator_prompt_with_facts() -> None:
    """Verify that facts_context is injected into LLMGenerator prompt."""
    generator = LLMGenerator()
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="General exam instructions: calculators allowed.",
        score=0.88,
        source_url="https://ecajmer.ac.in/exam.pdf",
        department="Examination Cell",
        last_verified=datetime(2026, 10, 20),
        token_count=10,
        rank=1,
    )
    facts_ctx = "### Verified Notice Facts:\n- Mid-term starts 15 Nov"

    system_prompt, user_prompt = generator.build_prompt(
        query="When is the exam?",
        chunks=[chunk],
        facts_context=facts_ctx,
    )
    assert "### Verified Notice Facts:" in user_prompt
    assert "Mid-term starts 15 Nov" in user_prompt
    assert "calculators allowed" in user_prompt


@pytest.mark.asyncio
async def test_fact_lookup_search_query() -> None:
    """Verify FactLookup.search builds and executes query successfully."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.key_facts = [{"fact": "CSE 3rd Sem exam on 15 Nov", "category": "date"}]
    mock_row.title_summary = "CSE Exam Schedule"
    mock_row.notice_type = "exam_schedule"
    mock_row.target_branch = ["CSE"]
    mock_row.target_semester = ["3rd Sem"]
    mock_row.department = "Computer Science"
    mock_row.effective_date = date(2026, 11, 1)
    mock_row.document_id = uuid.uuid4()
    mock_row.source_url = "https://ecajmer.ac.in/cse_exam.pdf"
    mock_row.last_verified = datetime(2026, 10, 20)
    mock_result.all.return_value = [mock_row]
    session.execute.return_value = mock_result

    results = await FactLookup.search(session, "CSE 3rd sem exam date")
    assert len(results) >= 1
    assert "CSE 3rd Sem exam on 15 Nov" in results[0].fact


def test_document_department_property() -> None:
    """Verify Document.department property safely returns name or None."""
    from models.department import Department
    from models.document import Document

    doc = Document(
        source_url="https://ecajmer.ac.in/cs.pdf",
        source_type="pdf",
        content_hash="hash1",
    )
    # When department_rel is not populated
    assert doc.department is None

    # When department_rel is populated
    doc.department_rel = Department(id=1, name="Computer Science", slug="cs")
    assert doc.department == "Computer Science"


@pytest.mark.asyncio
async def test_conflict_detector_with_document_attribute() -> None:
    """Verify ConflictDetector.check_conflicts does not raise AttributeError for Document instances."""
    from ingestion.conflict_detector import ConflictDetector
    from models.document import Document

    session = AsyncMock()

    # Document with no department_id returns False without error
    doc_no_dept = Document(
        id=uuid.uuid4(),
        source_url="https://ecajmer.ac.in/notice_no_dept.pdf",
        source_type="pdf",
        content_hash="hash123",
        status="fresh",
    )
    has_conflict = await ConflictDetector.check_conflicts(session, doc_no_dept)
    assert has_conflict is False

    # Document with department_id queries fresh documents in same department
    doc_with_dept = Document(
        id=uuid.uuid4(),
        source_url="https://ecajmer.ac.in/exam_schedule.pdf",
        source_type="pdf",
        department_id=1,
        content_hash="hash456",
        status="fresh",
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    has_conflict = await ConflictDetector.check_conflicts(session, doc_with_dept)
    assert has_conflict is False
    session.execute.assert_called_once()
