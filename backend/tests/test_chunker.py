from ingestion.chunker import SemanticChunker, chunk_document, count_tokens
from ingestion.schemas import ExtractedTable, FetchedDocument


def test_token_counter() -> None:
    """Test token counter accuracy for varying text lengths."""
    assert count_tokens("") == 0
    assert count_tokens("   ") == 0
    assert count_tokens("Engineering College Ajmer") == 3  # ~3 words * 1.33 = 3
    long_text = "This is a sentence with ten words describing the examination procedure."
    tokens = count_tokens(long_text)
    assert 10 <= tokens <= 20


def test_table_chunk_preservation() -> None:
    """Test that structured tables are preserved as intact individual chunks with row statements."""
    table = ExtractedTable(
        headers=["Day", "Subject", "Faculty", "Room"],
        rows=[
            ["Monday", "CS301", "Prof. Sharma", "Room 204"],
            ["Tuesday", "CS302", "Prof. Verma", "Lab 3"],
            ["Wednesday", "CS303", "Prof. Gupta", "Room 101"],
        ],
        title="CS Timetable 2026",
        page_number=1,
    )

    doc = FetchedDocument(
        source_url="https://ecajmer.ac.in/timetable.pdf",
        source_type="pdf",
        raw_content=b"dummy bytes",
        extracted_text="Some header text before table.",
        tables=[table],
        metadata={"title": "Official Timetable", "department": "CSE", "owner": "HOD"},
    )

    chunks = chunk_document(doc, department="CSE", owner="HOD")

    # Verify table chunk exists
    table_chunks = [c for c in chunks if c.metadata.get("is_table") is True]
    assert len(table_chunks) == 1

    t_chunk = table_chunks[0]
    assert "| Day | Subject | Faculty | Room |" in t_chunk.content
    assert "Day: Monday, Subject: CS301, Faculty: Prof. Sharma" in t_chunk.content
    assert t_chunk.metadata["department"] == "CSE"
    assert t_chunk.metadata["owner"] == "HOD"
    assert t_chunk.metadata["source_url"] == "https://ecajmer.ac.in/timetable.pdf"
    assert t_chunk.metadata["page_number"] == 1


def test_semantic_heading_and_paragraph_splitting() -> None:
    """Test paragraph grouping and semantic splitting across document sections."""
    text_sections = [
        "# Department of Computer Science",
        "The Department of Computer Science and Engineering was established in 1996. It offers B.Tech, M.Tech and PhD programs.",
        "## Academic Regulations",
        "Students are required to maintain a minimum of 75% attendance in all theory and laboratory courses.",
        "Failure to meet attendance requirements will result in debarment from the end-term examinations.",
        "## Examination Schedule",
        "The mid-semester examinations will commence on 14 September 2026 for all undergraduate students.",
        "Students must carry their official college ID cards to the examination hall.",
    ]

    doc = FetchedDocument(
        source_url="https://ecajmer.ac.in/cs_info.html",
        source_type="html",
        raw_content=b"dummy html bytes",
        extracted_text="\n\n".join(text_sections),
        tables=[],
        metadata={"title": "CSE Handbook", "department": "CSE"},
    )

    # Use small target token size to force multiple chunks
    chunker = SemanticChunker(target_tokens=50, min_tokens=20, max_tokens=100, overlap_ratio=0.2)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) >= 2
    assert all(c.token_count > 0 for c in chunks)
    assert all(c.metadata["department"] == "CSE" for c in chunks)
    assert all(c.metadata["source_url"] == "https://ecajmer.ac.in/cs_info.html" for c in chunks)


def test_sliding_window_overlap() -> None:
    """Test that sliding window overlap includes preceding context across adjacent chunks."""
    long_para_1 = (
        "Mid-term examination schedule has been finalized by the examination cell. "
        "Examinations will be held in two sessions daily from 10:00 AM to 1:00 PM and 2:00 PM to 5:00 PM. "
        "Seating plans will be displayed on the department notice board one hour prior to the examination."
    )
    long_para_2 = (
        "Fee payment deadline for the odd semester 2026-27 is 31 August 2026. "
        "Late fee of Rs 500 will be applicable for payments made after the deadline. "
        "All payments must be completed online through the college ERP portal."
    )

    doc = FetchedDocument(
        source_url="https://ecajmer.ac.in/notice.html",
        source_type="html",
        raw_content=b"dummy bytes",
        extracted_text=f"{long_para_1}\n\n{long_para_2}",
        tables=[],
    )

    chunker = SemanticChunker(target_tokens=35, min_tokens=15, max_tokens=80, overlap_ratio=0.25)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) >= 2
    # Second chunk should contain overlap from the end of the first paragraph
    assert (
        "Seating plans will be displayed" in chunks[1].content or "Fee payment" in chunks[1].content
    )


def test_oversized_paragraph_splitting() -> None:
    """Test that paragraphs exceeding max_tokens are split cleanly at sentence boundaries."""
    sentences = [
        f"This is sentence number {i} providing institutional details." for i in range(1, 30)
    ]
    oversized_para = " ".join(sentences)

    doc = FetchedDocument(
        source_url="https://ecajmer.ac.in/long_notice.pdf",
        source_type="pdf",
        raw_content=b"dummy bytes",
        extracted_text=oversized_para,
        tables=[],
    )

    chunker = SemanticChunker(target_tokens=60, min_tokens=20, max_tokens=80, overlap_ratio=0.15)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) >= 3
    for chunk in chunks:
        assert chunk.token_count <= 100
        assert chunk.content.endswith(".")
