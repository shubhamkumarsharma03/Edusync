import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ingestion.chunker import SemanticChunker, extract_document_date, infer_doc_type
from ingestion.ocr import DocumentOCR
from ingestion.ocr_baidu import BaiduPaddleOCRClient
from ingestion.schemas import ExtractedTable, FetchedDocument
from ingestion.table_extractor import (
    normalize_table_dimensions,
    parse_markdown_tables,
    validate_table,
)

# ---------------------------------------------------------------------------
# 1. Table Extractor & Validator Tests
# ---------------------------------------------------------------------------


def test_parse_markdown_tables_basic():
    md = """
## Examination Schedule

| Date | Subject | Time | Room |
|---|---|---|---|
| 2026-09-15 | Data Structures | 10:00 AM | Room 101 |
| 2026-09-17 | Operating Systems | 02:00 PM | Room 102 |

Notice: Please bring your ID card.
"""
    tables = parse_markdown_tables(md, page_number=1)
    assert len(tables) == 1
    t = tables[0]
    assert t.page_number == 1
    assert t.title == "Examination Schedule"
    assert t.headers == ["Date", "Subject", "Time", "Room"]
    assert len(t.rows) == 2
    assert t.rows[0] == ["2026-09-15", "Data Structures", "10:00 AM", "Room 101"]
    assert t.rows[1] == ["2026-09-17", "Operating Systems", "02:00 PM", "Room 102"]

    # Verify Markdown roundtrip
    rendered_md = t.to_markdown()
    assert "| Date | Subject | Time | Room |" in rendered_md

    # Verify row statements for RAG vector search
    statements = t.to_row_statements()
    assert len(statements) == 2
    assert "Subject: Data Structures" in statements[0]
    assert "Room: Room 101" in statements[0]


def test_normalize_table_dimensions_uneven_rows():
    headers = ["A", "B"]
    rows = [["1"], ["1", "2", "3"]]  # One row short, one row long
    norm_headers, norm_rows = normalize_table_dimensions(headers, rows)

    assert len(norm_headers) == 3
    assert norm_headers == ["A", "B", "Col 3"]
    assert norm_rows[0] == ["1", "", ""]
    assert norm_rows[1] == ["1", "2", "3"]


def test_validate_table_rules():
    # Valid table
    valid_t = ExtractedTable(headers=["A", "B"], rows=[["1", "2"]])
    is_valid, _ = validate_table(valid_t)
    assert is_valid is True

    # Empty table
    empty_t = ExtractedTable(headers=[], rows=[])
    is_valid, reason = validate_table(empty_t)
    assert is_valid is False

    # Fewer than 2 columns
    single_col_t = ExtractedTable(headers=["A"], rows=[["1"]])
    is_valid, reason = validate_table(single_col_t)
    assert is_valid is False
    assert "fewer than 2 columns" in reason.lower()

    # Empty rows
    empty_rows_t = ExtractedTable(headers=["A", "B"], rows=[["", ""]])
    is_valid, reason = validate_table(empty_rows_t)
    assert is_valid is False


# ---------------------------------------------------------------------------
# 2. Baidu OCR Client Tests (Async Job & Direct Serving)
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_cache_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_baidu_client(temp_cache_dir):
    client = BaiduPaddleOCRClient()
    client.cache_dir = temp_cache_dir
    client.token = "mock_test_token_12345"
    client.poll_interval = 0.01  # Fast polling for test
    return client


@pytest.mark.asyncio
async def test_baidu_async_job_flow(mock_baidu_client):
    """Test full async job submission -> polling -> jsonl download -> markdown/table extraction."""
    mock_baidu_client.mode = "async_job"

    sample_pdf_bytes = b"%PDF-1.4 Mock Scanned Timetable PDF Content"
    mock_job_id = "job-abc-789"
    mock_jsonl_content = json.dumps(
        {
            "result": {
                "layoutParsingResults": [
                    {
                        "markdown": {
                            "text": "## CS Sem 5 Timetable\n\n| Day | Time | Subject |\n|---|---|---|\n| Mon | 09:00 | Database Systems |\n",
                            "images": {},
                        },
                        "outputImages": {},
                    }
                ]
            }
        }
    )

    # Mock HTTP calls
    with patch("httpx.AsyncClient.post") as mock_post, patch("httpx.AsyncClient.get") as mock_get:
        # 1. Job submission response
        sub_resp = AsyncMock()
        sub_resp.status_code = 200
        sub_resp.json.return_value = {"code": 0, "data": {"jobId": mock_job_id}}
        mock_post.return_value = sub_resp

        # 2. Polling status responses (pending -> done)
        poll_resp_pending = AsyncMock()
        poll_resp_pending.status_code = 200
        poll_resp_pending.json.return_value = {"data": {"state": "pending"}}

        poll_resp_done = AsyncMock()
        poll_resp_done.status_code = 200
        poll_resp_done.json.return_value = {
            "data": {
                "state": "done",
                "resultUrl": {"jsonUrl": "https://example.com/result.jsonl"},
            }
        }

        # 3. JSONL download response
        jsonl_resp = AsyncMock()
        jsonl_resp.status_code = 200
        jsonl_resp.raise_for_status = lambda: None
        jsonl_resp.text = mock_jsonl_content

        mock_get.side_effect = [poll_resp_pending, poll_resp_done, jsonl_resp]

        doc_result = await mock_baidu_client.process_document(
            file_input=sample_pdf_bytes,
            is_pdf=True,
        )

        assert doc_result.total_pages == 1
        assert "CS Sem 5 Timetable" in doc_result.combined_markdown
        assert len(doc_result.tables) == 1
        assert doc_result.tables[0].headers == ["Day", "Time", "Subject"]
        assert doc_result.tables[0].rows[0] == ["Mon", "09:00", "Database Systems"]


@pytest.mark.asyncio
async def test_baidu_serving_flow(mock_baidu_client):
    """Test direct serving (POST /ocr) with Base64 payload and immediate response."""
    mock_baidu_client.mode = "serving"
    sample_img_bytes = b"MOCK_PNG_IMAGE_BYTES"

    mock_serving_response = {
        "errorCode": 0,
        "errorMsg": "Success",
        "result": {
            "ocrResults": [
                {
                    "prunedResult": {
                        "markdown": {
                            "text": "### Fee Circular\nAll students must clear semester dues by Sept 25."
                        }
                    }
                }
            ]
        },
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        resp = AsyncMock()
        resp.status_code = 200
        resp.json.return_value = mock_serving_response
        mock_post.return_value = resp

        doc_result = await mock_baidu_client.process_document(
            file_input=sample_img_bytes,
            is_pdf=False,
        )

        assert doc_result.total_pages == 1
        assert "Fee Circular" in doc_result.combined_markdown
        assert "semester dues by Sept 25" in doc_result.combined_markdown


@pytest.mark.asyncio
async def test_baidu_disk_cache_roundtrip(mock_baidu_client, temp_cache_dir):
    """Verify that parsed results are saved to disk and loaded without network requests."""
    mock_baidu_client.mode = "serving"
    sample_bytes = b"CACHE_TEST_SAMPLE_DOC_BYTES"
    cache_h = hashlib.sha256(sample_bytes).hexdigest()

    mock_serving_response = {
        "errorCode": 0,
        "errorMsg": "Success",
        "result": {
            "ocrResults": [{"prunedResult": {"markdown": {"text": "CACHED DOCUMENT TEXT"}}}]
        },
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        resp = AsyncMock()
        resp.status_code = 200
        resp.json.return_value = mock_serving_response
        mock_post.return_value = resp

        # 1. First run executes OCR and writes to disk
        res1 = await mock_baidu_client.process_document(sample_bytes, is_pdf=False)
        assert "CACHED DOCUMENT TEXT" in res1.combined_markdown
        assert mock_post.call_count == 1

        # Verify disk cache file exists
        cache_file = temp_cache_dir / f"baidu_{cache_h}.json"
        assert cache_file.exists()

        # 2. Fresh client instance (empty memory cache) with same disk directory
        new_client = BaiduPaddleOCRClient()
        new_client.cache_dir = temp_cache_dir
        new_client.token = "mock_token"

        res2 = await new_client.process_document(sample_bytes, is_pdf=False)
        assert "CACHED DOCUMENT TEXT" in res2.combined_markdown
        # Network post must NOT be called again
        assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# 3. Unified OCR Service Routing & Fallback Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_ocr_routes_to_baidu_when_configured():
    """Verify DocumentOCR delegates to Baidu client when active."""
    ocr = DocumentOCR()
    ocr.baidu_client.token = "valid_token"

    with patch.object(ocr.baidu_client, "process_document") as mock_baidu:
        mock_res = AsyncMock()
        mock_res.combined_markdown = "BAIDU EXTRACTED TEXT"
        mock_res.tables = [ExtractedTable(headers=["A", "B"], rows=[["1", "2"]])]
        mock_baidu.return_value = mock_res

        text, tables = await ocr.extract_document(b"SAMPLE_BYTES", is_pdf=True)
        assert text == "BAIDU EXTRACTED TEXT"
        assert len(tables) == 1
        mock_baidu.assert_called_once()


@pytest.mark.asyncio
async def test_unified_ocr_graceful_fallback_to_local_got(temp_cache_dir):
    """Verify DocumentOCR falls back to local GOT-OCR when Baidu is unconfigured or errors."""
    ocr = DocumentOCR()
    ocr.cache_dir = temp_cache_dir
    ocr.baidu_client.token = None  # No cloud token

    assert ocr.is_baidu_active is False

    import io

    from PIL import Image

    test_img = Image.new("RGB", (20, 20), color=(255, 255, 255))
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    valid_img_bytes = buf.getvalue()

    with patch.object(ocr, "_ocr_image_sync", return_value="LOCAL GOT-OCR OUTPUT") as mock_local:
        text = await ocr.extract_text_from_image(valid_img_bytes)
        assert text == "LOCAL GOT-OCR OUTPUT"
        mock_local.assert_called_once()


# ---------------------------------------------------------------------------
# 4. Semantic Chunker & Rich Metadata Enrichment Tests
# ---------------------------------------------------------------------------


def test_infer_doc_type():
    assert infer_doc_type("CS Sem 5 Schedule", "https://ecajmer.ac.in/tt.pdf", "") == "timetable"
    assert (
        infer_doc_type("Office Order No 10", "https://ecajmer.ac.in/circulars/1", "") == "circular"
    )
    assert infer_doc_type("Hostel Fee Notice", "https://ecajmer.ac.in/fee.pdf", "") == "fee_notice"
    assert (
        infer_doc_type("B.Tech CSE Syllabus", "https://ecajmer.ac.in/scheme.pdf", "") == "syllabus"
    )
    assert (
        infer_doc_type("Mid Term Examination", "https://ecajmer.ac.in/exam.pdf", "")
        == "exam_notice"
    )
    assert infer_doc_type("Library Rules", "https://ecajmer.ac.in/library.pdf", "") == "notice"


def test_extract_document_date():
    assert extract_document_date("Ref: ECA/2026/101  Date: 15-09-2026\nNotice") == "15-09-2026"
    assert extract_document_date("Dated: 12 September 2026\nOffice Order") == "12 September 2026"
    assert (
        extract_document_date("Circular\nSeptember 20, 2026\nAll students...")
        == "September 20, 2026"
    )
    assert extract_document_date("No date mentioned in this header.") is None


def test_chunker_isolates_markdown_tables_and_adds_metadata():
    """Verify markdown tables from OCR become dedicated chunks with row statements and metadata."""
    sample_text = """
## Department Notice
All students must adhere to the weekly schedule below. Date: 10-09-2026.

| Day | Subject | Faculty | Room |
|---|---|---|---|
| Mon | Algorithms | Dr. Gupta | LT-1 |
| Wed | Computer Networks | Prof. Verma | LT-2 |

## General Guidelines
Please arrive 5 minutes before class starts.
"""
    doc = FetchedDocument(
        source_url="https://ecajmer.ac.in/departments/cs-it/timetables/sem5.pdf",
        source_type="pdf",
        raw_content=b"MOCK_CONTENT",
        extracted_text=sample_text,
        tables=[],
        metadata={"title": "CS Sem 5 Timetable", "department": "Computer Science"},
    )

    chunker = SemanticChunker(target_tokens=300)
    chunks = chunker.chunk_document(doc)

    # 1. Verify table chunk exists and is isolated
    table_chunks = [c for c in chunks if c.metadata.get("is_table") is True]
    assert len(table_chunks) == 1
    t_chunk = table_chunks[0]

    assert "### Table 1" in t_chunk.content
    assert "| Day | Subject | Faculty | Room |" in t_chunk.content
    assert "Row Statements:" in t_chunk.content
    assert "Subject: Algorithms" in t_chunk.content
    assert "Faculty: Dr. Gupta" in t_chunk.content

    # 2. Verify metadata enrichment
    assert t_chunk.metadata.get("doc_type") == "timetable"
    assert t_chunk.metadata.get("document_date") == "10-09-2026"
    assert t_chunk.metadata.get("department") == "Computer Science"

    # 3. Verify text chunk metadata
    text_chunks = [c for c in chunks if c.metadata.get("is_table") is False]
    assert len(text_chunks) >= 1
    assert text_chunks[0].metadata.get("doc_type") == "timetable"
    assert text_chunks[0].metadata.get("document_date") == "10-09-2026"
