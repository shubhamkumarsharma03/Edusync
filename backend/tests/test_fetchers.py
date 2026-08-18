import os
import tempfile
from collections.abc import Generator

import pymupdf as fitz
import pytest

from ingestion import (
    ExtractedTable,
    FetchedDocument,
    detect_source_type,
    fetch_document,
    fetch_html,
    fetch_pdf,
    fetch_sheet,
    get_fetcher,
)
from ingestion.fetchers.html_fetcher import HTMLFetcher
from ingestion.fetchers.pdf_fetcher import PDFFetcher
from ingestion.fetchers.sheet_fetcher import SheetFetcher


@pytest.fixture
def sample_pdf_file() -> Generator[str, None, None]:
    """Create a temporary valid PDF file with text and metadata."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Engineering College Ajmer\nDepartment of Computer Science\nMid-Term Examination Notice 2026",
    )
    doc.set_metadata({"title": "Exam Schedule 2026", "author": "Examination Cell"})

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        temp_path = f.name
    doc.save(temp_path)
    doc.close()

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def sample_csv_file() -> Generator[str, None, None]:
    """Create a temporary CSV file with tabular timetable data."""
    content = "Day,Period,Subject,Faculty,Room\nMonday,1,CS301,Prof. Sharma,Room 204\nTuesday,2,CS302,Prof. Verma,Lab 3\n"
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
        temp_path = f.name
        f.write(content)

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def sample_html_file() -> Generator[str, None, None]:
    """Create a temporary HTML file with boilerplate, notice table, and PDF download links."""
    html_content = """<!DOCTYPE html>
    <html>
    <head><title>ECA Notice Board</title><style>.nav { color: red; }</style></head>
    <body>
        <nav><a href="/">Home</a><a href="/about">About</a></nav>
        <header><h1>Header Banner</h1></header>
        <main>
            <h2>Official Announcements</h2>
            <p>Please find below the latest departmental circulars for Sem 7.</p>
            <table>
                <tr><th>Date</th><th>Circular</th><th>Download</th></tr>
                <tr><td>2026-08-15</td><td>Fee Notice</td><td><a href="/files/fee_notice_2026.pdf">PDF Link</a></td></tr>
                <tr><td>2026-08-18</td><td>Exam Time Table</td><td><a href="/circulars/exam_tt.pdf">Download</a></td></tr>
            </table>
        </main>
        <footer><p>Copyright 2026 ECA</p></footer>
        <script>console.log("tracker");</script>
    </body>
    </html>
    """
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False, encoding="utf-8") as f:
        temp_path = f.name
        f.write(html_content)

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_extracted_table_formatting() -> None:
    """Test ExtractedTable markdown generation and row statements."""
    table = ExtractedTable(
        headers=["Day", "Subject", "Room"],
        rows=[["Monday", "CS301", "204"], ["Tuesday", "CS302", "Lab 1"]],
        title="Class Schedule",
    )

    md = table.to_markdown()
    assert "| Day | Subject | Room |" in md
    assert "| Monday | CS301 | 204 |" in md

    statements = table.to_row_statements()
    assert len(statements) == 2
    assert "Day: Monday, Subject: CS301, Room: 204" in statements[0]
    assert "Day: Tuesday, Subject: CS302, Room: Lab 1" in statements[1]


@pytest.mark.asyncio
async def test_pdf_fetcher(sample_pdf_file: str) -> None:
    """Test PDF fetching, text extraction, and metadata parsing."""
    doc: FetchedDocument = await fetch_pdf(sample_pdf_file)

    assert doc.source_type == "pdf"
    assert "Mid-Term Examination Notice 2026" in doc.extracted_text
    assert doc.metadata["page_count"] == 1
    assert doc.metadata["title"] == "Exam Schedule 2026"
    assert len(doc.raw_content) > 0


@pytest.mark.asyncio
async def test_html_fetcher(sample_html_file: str) -> None:
    """Test HTML fetching, boilerplate removal, table parsing, and PDF link discovery."""
    doc: FetchedDocument = await fetch_html(sample_html_file)

    assert doc.source_type == "html"
    assert "## Official Announcements" in doc.extracted_text
    assert "tracker" not in doc.extracted_text  # Script tag stripped
    assert "Header Banner" not in doc.extracted_text  # Header stripped
    assert "Copyright 2026" not in doc.extracted_text  # Footer stripped

    # Table verification
    assert len(doc.tables) >= 1
    assert doc.tables[0].headers == ["Date", "Circular", "Download"]

    # Discovered PDF links verification (ADR-012)
    discovered = doc.metadata.get("discovered_pdf_links", [])
    assert any("fee_notice_2026.pdf" in link for link in discovered)
    assert any("exam_tt.pdf" in link for link in discovered)


@pytest.mark.asyncio
async def test_sheet_fetcher(sample_csv_file: str) -> None:
    """Test Sheet/CSV fetching, header detection, and row statement normalization."""
    doc: FetchedDocument = await fetch_sheet(sample_csv_file, title="CS Timetable")

    assert doc.source_type == "sheet"
    assert doc.metadata["row_count"] == 2
    assert doc.metadata["column_count"] == 5
    assert "Monday" in doc.extracted_text
    assert "Prof. Sharma" in doc.extracted_text
    assert "Day: Monday" in doc.extracted_text
    assert len(doc.tables) == 1


def test_factory_and_source_detection() -> None:
    """Test source type detection heuristic and fetcher factory."""
    assert detect_source_type("https://ecajmer.ac.in/notices/exam.pdf") == "pdf"
    assert detect_source_type("https://ecajmer.ac.in/cs-department.html") == "html"
    assert detect_source_type("data/fees.csv") == "sheet"
    assert detect_source_type("data/timetable.xlsx") == "sheet"

    pdf_fetcher = get_fetcher("test.pdf")
    assert isinstance(pdf_fetcher, PDFFetcher)

    html_fetcher = get_fetcher("test.html")
    assert isinstance(html_fetcher, HTMLFetcher)

    sheet_fetcher = get_fetcher("test.csv")
    assert isinstance(sheet_fetcher, SheetFetcher)


@pytest.mark.asyncio
async def test_unified_fetch_document(sample_pdf_file: str) -> None:
    """Test unified fetch_document entry point."""
    doc = await fetch_document(sample_pdf_file)
    assert doc.source_type == "pdf"
    assert len(doc.raw_content) > 0


@pytest.mark.asyncio
async def test_corrupted_pdf_error() -> None:
    """Test error handling when encountering corrupted PDF bytes."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"NOT_A_VALID_PDF_STREAM")
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="Invalid or corrupted PDF document"):
            await fetch_pdf(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
