from ingestion.chunker import (
    SemanticChunker,
    extract_academic_year,
    extract_notice_sno,
    extract_semester,
)
from ingestion.schemas import FetchedDocument


def test_entity_extraction_helpers() -> None:
    """Test regex extraction of semester, notice serial number, and academic year."""
    # Semester tests
    assert extract_semester("Notice for B.Tech III Sem students") == "3rd Sem"
    assert extract_semester("Registration for 4th Semester 2026") == "4th Sem"
    assert extract_semester("Class commencement for 1st Sem") == "1st Sem"
    assert extract_semester("Final year VIIIth semester project submission") == "8th Sem"
    assert extract_semester("General faculty meeting notice") is None

    # Notice S.No. tests
    assert extract_semester("No. ECA/Acad/2026/1042") is None
    assert extract_notice_sno("Ref: ECA/Acad/2026/1042 dated 12/08/2026") == "ECA/Acad/2026/1042"
    assert extract_notice_sno("Order No. F.(2)/Admin/Estt/2025/89") == "F.(2)/Admin/Estt/2025/89"

    # Academic Year tests
    assert extract_academic_year("Session 2025-26 enrollment details") == "2025-26"
    assert extract_academic_year("Academic Year 2026-2027 Fee Structure") == "2026-2027"


def test_markdown_heading_hierarchy_breadcrumbs() -> None:
    """Test that nested Markdown headings produce breadcrumb hierarchy context."""
    chunker = SemanticChunker(target_tokens=300, min_tokens=50, max_tokens=600)

    sample_markdown = """# Engineering College Ajmer
Notice No: ECA/Acad/2026/501
Session: 2025-26

## Academic Section Guidelines

### III Semester Registration Rules
All III Sem students must complete registration before September 20, 2026.
Late fees will apply after the designated deadline.

### Examination Schedule
The mid-term examination for 3rd semester will commence from October 15, 2026.

## Proctor Section Anti-Ragging Directives
Strict compliance with UGC anti-ragging regulations is mandatory for all students on campus.
"""

    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/notice_501.pdf",
        source_type="pdf",
        metadata={"content_hash": "dummyhash123"},
        raw_content=sample_markdown.encode("utf-8"),
        extracted_text=sample_markdown,
    )

    chunks = chunker.chunk_document(fetched)

    assert len(chunks) >= 2

    # Check third semester chunk has breadcrumbs and metadata
    reg_chunks = [
        c
        for c in chunks
        if "III Semester Registration Rules" in c.content or "September 20, 2026" in c.content
    ]
    assert len(reg_chunks) > 0
    first_reg = reg_chunks[0]

    # Content must include breadcrumb context header
    assert (
        "[Context: Engineering College Ajmer > Academic Section Guidelines > III Semester Registration Rules]"
        in first_reg.content
    )
    assert first_reg.metadata.get("semester") == "3rd Sem"
    assert first_reg.metadata.get("notice_sno") == "ECA/Acad/2026/501"
    assert first_reg.metadata.get("academic_year") == "2025-26"

    # Check proctor section chunk has breadcrumbs
    proctor_chunks = [c for c in chunks if "anti-ragging regulations" in c.content]
    assert len(proctor_chunks) > 0
    first_proctor = proctor_chunks[0]
    assert (
        "[Context: Engineering College Ajmer > Proctor Section Anti-Ragging Directives]"
        in first_proctor.content
    )


def test_markdown_tables_remain_atomic_with_breadcrumbs() -> None:
    """Test that Markdown tables are kept intact with breadcrumb headers prepended."""
    chunker = SemanticChunker(target_tokens=300, min_tokens=50, max_tokens=800)

    table_markdown = """# Department of Computer Science & Engineering

## Time Table III Sem 2025-26

| Day | 9:00 - 10:00 | 10:00 - 11:00 | Room |
| --- | --- | --- | --- |
| Monday | DSA | OOPS | S-9 |
| Tuesday | Digital Electronics | COA | NB-111 |
| Wednesday | Mathematics III | DSA | S-9 |
"""

    fetched = FetchedDocument(
        source_url="https://ecajmer.ac.in/timetable_cse.pdf",
        source_type="pdf",
        metadata={"content_hash": "dummyhash456"},
        raw_content=table_markdown.encode("utf-8"),
        extracted_text=table_markdown,
    )

    chunks = chunker.chunk_document(fetched)
    assert len(chunks) >= 1

    table_chunk = chunks[0]
    assert (
        "[Context: Department of Computer Science & Engineering > Time Table III Sem 2025-26]"
        in table_chunk.content
    )
    assert "| Monday | DSA | OOPS | S-9 |" in table_chunk.content
    assert table_chunk.metadata.get("semester") == "3rd Sem"
