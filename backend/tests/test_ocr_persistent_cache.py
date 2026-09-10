import hashlib
import io
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from ingestion.fetchers.ecajmer_fetcher import ECAjmerFetcher
from ingestion.fetchers.pdf_fetcher import PDFFetcher
from ingestion.ocr import DocumentOCR


@pytest.fixture
def temp_cache_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_ocr_disk_cache_roundtrip(temp_cache_dir):
    """Test that OCR text is saved to disk and loaded from disk on subsequent requests."""
    ocr = DocumentOCR()
    ocr.cache_dir = temp_cache_dir

    test_img = Image.new("RGB", (60, 60), color=(200, 200, 200))
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    cache_key = hashlib.sha256(img_bytes).hexdigest()

    # 1. First run: mock model inference to return extracted text
    with patch.object(ocr, "_ocr_image_sync", return_value="FIRST RUN EXTRACTED TEXT") as mock_sync:
        result = await ocr.extract_text_from_image(img_bytes)
        assert result == "FIRST RUN EXTRACTED TEXT"
        assert mock_sync.call_count == 1

    # Verify written to disk cache
    cache_file = temp_cache_dir / f"{cache_key}.txt"
    assert cache_file.exists()
    assert cache_file.read_text(encoding="utf-8") == "FIRST RUN EXTRACTED TEXT"

    # 2. Simulate fresh server instance (empty memory cache) with same disk cache
    new_ocr = DocumentOCR()
    new_ocr.cache_dir = temp_cache_dir
    assert cache_key not in new_ocr._cache

    with patch.object(new_ocr, "_ocr_image_sync") as mock_sync:
        cached_result = await new_ocr.extract_text_from_image(img_bytes)
        assert cached_result == "FIRST RUN EXTRACTED TEXT"
        # Must NOT call _ocr_image_sync because it was a disk cache hit
        mock_sync.assert_not_called()
        # Memory cache should now also be populated
        assert new_ocr._cache[cache_key] == "FIRST RUN EXTRACTED TEXT"


@pytest.mark.asyncio
async def test_pdf_fetcher_fast_path_existing_hash():
    """Test that PDFFetcher skips fitz parsing and OCR if existing_hash matches binary."""
    fetcher = PDFFetcher()
    fake_pdf = b"%PDF-1.4 Mock Binary Content"
    fake_hash = hashlib.sha256(fake_pdf).hexdigest()

    with patch.object(fetcher, "_get_raw_bytes", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = (fake_pdf, {"title": "Test Doc"})

        with patch("ingestion.fetchers.pdf_fetcher.fitz.open") as mock_fitz:
            doc = await fetcher.fetch("https://example.com/notice.pdf", existing_hash=fake_hash)
            assert doc.source_url == "https://example.com/notice.pdf"
            assert doc.raw_content == fake_pdf
            assert doc.extracted_text == ""
            # fitz.open should NOT be called since binary hash matched existing record
            mock_fitz.assert_not_called()


@pytest.mark.asyncio
async def test_ecajmer_fetcher_fast_path_existing_hash():
    """Test that ECAjmerFetcher skips fitz parsing and OCR if existing_hash matches."""
    fetcher = ECAjmerFetcher()
    fake_pdf = b"%PDF-1.4 Mock Circular Content"
    fake_hash = hashlib.sha256(fake_pdf).hexdigest()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_pdf
        mock_get.return_value = mock_resp

        with patch("ingestion.fetchers.ecajmer_fetcher.fitz.open") as mock_fitz:
            raw_bytes, text, tables, p_count = await fetcher.fetch_pdf_content(
                "https://ecajmer.ac.in/notice.pdf", existing_hash=fake_hash
            )
            assert raw_bytes == fake_pdf
            assert text == ""
            assert tables == []
            mock_fitz.assert_not_called()


@pytest.mark.asyncio
async def test_ecajmer_fetcher_max_ocr_pages_limit():
    """Test that ECAjmerFetcher respects max_ocr_pages ceiling on multi-page scanned PDFs."""
    fetcher = ECAjmerFetcher()
    fake_pdf = b"%PDF-1.4 Mock Multi-page PDF"

    # Mock fitz doc with 5 scanned pages (text length < 40)
    mock_pages = []
    for _ in range(5):
        page = MagicMock()
        page.get_text.return_value = ""
        pix = MagicMock()
        pix.tobytes.return_value = b"fake_png"
        page.get_pixmap.return_value = pix
        page.find_tables.return_value = []
        mock_pages.append(page)

    mock_doc = MagicMock()
    mock_doc.__len__.return_value = len(mock_pages)
    mock_doc.__getitem__.side_effect = lambda idx: mock_pages[idx]
    mock_doc.__enter__.return_value = mock_doc
    mock_doc.__exit__.return_value = None

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_pdf
        mock_get.return_value = mock_resp

        with patch("ingestion.fetchers.ecajmer_fetcher.fitz.open", return_value=mock_doc):
            with patch("ingestion.fetchers.ecajmer_fetcher.ocr_service.extract_text_from_image", new_callable=AsyncMock) as mock_ocr:
                mock_ocr.return_value = "Extracted OCR text"
                # Limit to 2 OCR pages max
                raw_bytes, text, tables, p_count = await fetcher.fetch_pdf_content(
                    "https://ecajmer.ac.in/notice.pdf", max_ocr_pages=2
                )
                assert p_count == 5
                # ocr should only be called twice, not 5 times
                assert mock_ocr.call_count == 2
