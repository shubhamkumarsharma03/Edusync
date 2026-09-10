import io
from unittest.mock import patch

import pytest
from PIL import Image

from api.config import get_settings
from ingestion.ocr import DocumentOCR


@pytest.fixture
def ocr_instance(tmp_path):
    ocr = DocumentOCR()
    ocr.cache_dir = tmp_path
    return ocr


def test_ocr_is_available(ocr_instance):
    """Local GOT-OCR is always available without external cloud credentials."""
    assert ocr_instance.is_available is True


def test_ocr_configurable_defaults(ocr_instance):
    """Verify parameters are loaded from Settings and are configurable."""
    settings = get_settings()
    assert ocr_instance.model_id == settings.GOT_OCR_MODEL_ID
    assert ocr_instance.max_tokens == settings.GOT_OCR_MAX_TOKENS
    assert ocr_instance.dpi == settings.GOT_OCR_DPI
    assert ocr_instance.min_text_threshold == settings.OCR_MIN_TEXT_THRESHOLD
    assert ocr_instance.format_output == settings.GOT_OCR_FORMAT


@pytest.mark.asyncio
async def test_ocr_empty_input(ocr_instance):
    """Empty image input should return empty string."""
    result = await ocr_instance.extract_text_from_image(b"")
    assert result == ""


@pytest.mark.asyncio
async def test_ocr_unsupported_type(ocr_instance):
    """Unsupported object type should raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported image input type"):
        await ocr_instance.extract_text_from_image(12345)  # type: ignore


@pytest.mark.asyncio
async def test_ocr_cache_hit(ocr_instance):
    """Cached images should immediately return cached text without model inference."""
    test_img = Image.new("RGB", (50, 50), color=(255, 255, 255))
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    import hashlib
    h = hashlib.sha256(img_bytes).hexdigest()
    ocr_instance._cache[h] = "CACHED CIRCULAR CONTENT"

    # With cache hit, _ocr_image_sync should never be called
    with patch.object(ocr_instance, "_ocr_image_sync") as mock_sync:
        result = await ocr_instance.extract_text_from_image(img_bytes)
        assert result == "CACHED CIRCULAR CONTENT"
        mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_extracts_and_populates_cache(ocr_instance):
    """Successful OCR extraction should store the result in the in-memory cache."""
    test_img = Image.new("RGB", (50, 50), color=(200, 200, 200))
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    with patch.object(ocr_instance, "_ocr_image_sync", return_value="ENGINEERING COLLEGE AJMER NOTICE") as mock_sync:
        result = await ocr_instance.extract_text_from_image(img_bytes, page_number=1, doc_name="notice.png")
        assert result == "ENGINEERING COLLEGE AJMER NOTICE"
        mock_sync.assert_called_once()

    # Second call should hit the cache
    with patch.object(ocr_instance, "_ocr_image_sync") as mock_sync_second:
        cached_result = await ocr_instance.extract_text_from_image(img_bytes)
        assert cached_result == "ENGINEERING COLLEGE AJMER NOTICE"
        mock_sync_second.assert_not_called()


def test_zero_cloud_ocr_imports():
    """Verify that no cloud OCR libraries (Google Vision, AWS Textract, Azure OCR) are imported."""
    import sys
    for mod_name in sys.modules:
        assert "google.cloud.vision" not in mod_name
        assert "textract" not in mod_name
        assert "azure.cognitiveservices.vision" not in mod_name
