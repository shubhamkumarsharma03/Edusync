from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.fetchers.ecajmer_fetcher import ECAjmerFetcher


def test_parse_url_department_circulars():
    url = "https://www.ecajmer.ac.in/departments/cs-it/circulars"
    slug, category_id, dept = ECAjmerFetcher.parse_url(url)
    assert slug == "cs-it"
    assert category_id == 1
    assert dept == "Computer Science and Engineering"


def test_parse_url_department_timetable():
    url = "https://www.ecajmer.ac.in/departments/ce/timetable"
    slug, category_id, dept = ECAjmerFetcher.parse_url(url)
    assert slug == "ce"
    assert category_id == 2
    assert dept == "Civil Engineering"


def test_parse_url_cell_circulars():
    url = "https://www.ecajmer.ac.in/ui/cells/registrar/circulars"
    slug, category_id, cell_name = ECAjmerFetcher.parse_url(url)
    assert slug == "registrar"
    assert category_id == 1
    assert cell_name == "Registrar Section"


@pytest.mark.asyncio
async def test_fetch_circular_entries_mocked():
    fetcher = ECAjmerFetcher()

    mock_entries = [
        {
            "id": 101,
            "sno": "2026WEB001",
            "date": "2026-08-20",
            "title": "Exam Schedule Mid-Term",
            "content": "uploads/circulars/exam.pdf",
            "createdAt": "2026-08-20T00:00:00.000Z",
        }
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(
            return_value={
                "success": True,
                "data": mock_entries,
                "pagination": {"totalItems": 1},
            }
        )
        mock_get.return_value = mock_resp

        entries = await fetcher.fetch_circular_entries("cs-it", category_id=1, limit=50)
        assert len(entries) == 1
        assert entries[0]["sno"] == "2026WEB001"


@pytest.mark.asyncio
async def test_fetch_single_notice_structure():
    fetcher = ECAjmerFetcher()

    entry = {
        "id": 202,
        "sno": "2026WEB002",
        "date": "2026-08-22",
        "title": "Project Submission Notice",
        "content": "uploads/circulars/project.pdf",
        "createdAt": "2026-08-22T00:00:00.000Z",
    }

    with patch.object(fetcher, "fetch_pdf_content", new_callable=AsyncMock) as mock_pdf:
        mock_pdf.return_value = (b"%PDF-mock", "Project Guidelines Page 1", [], 1)

        doc = await fetcher.fetch_single_notice(
            entry, department_name="Computer Science and Engineering"
        )
        assert doc.source_type == "pdf"
        assert "Project Submission Notice" in doc.extracted_text
        assert "2026WEB002" in doc.extracted_text
        assert "Project Guidelines Page 1" in doc.extracted_text
        assert doc.metadata["sno"] == "2026WEB002"
        assert doc.metadata["department"] == "Computer Science and Engineering"
