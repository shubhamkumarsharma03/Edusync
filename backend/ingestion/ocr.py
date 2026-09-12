import asyncio
import hashlib
import io
import logging
from pathlib import Path
from typing import Any

from PIL import Image

from api.config import get_settings
from ingestion.ocr_baidu import baidu_ocr_client
from ingestion.schemas import ExtractedTable

logger = logging.getLogger(__name__)


class DocumentOCR:
    """Unified OCR Service for EduSync.

    Routes to Baidu PaddleOCR (AI Studio) when configured, and falls back to
    local, offline GOT-OCR 2.0 when cloud services are unavailable or offline.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider: str = getattr(self.settings, "OCR_PROVIDER", "auto").lower()

        # Baidu client reference
        self.baidu_client = baidu_ocr_client

        # Local GOT-OCR settings
        self.model_id: str = getattr(self.settings, "GOT_OCR_MODEL_ID", "stepfun-ai/GOT-OCR-2.0-hf")
        self.configured_device: str = getattr(self.settings, "GOT_OCR_DEVICE", "auto")
        self.max_tokens: int = getattr(self.settings, "GOT_OCR_MAX_TOKENS", 2048)
        self.dpi: int = getattr(self.settings, "GOT_OCR_DPI", 150)
        self.min_text_threshold: int = getattr(self.settings, "OCR_MIN_TEXT_THRESHOLD", 40)
        self.format_output: bool = getattr(self.settings, "GOT_OCR_FORMAT", True)

        raw_cache_dir = getattr(self.settings, "GOT_OCR_CACHE_DIR", "models_cache/ocr_cache")
        cache_path = Path(raw_cache_dir)
        if not cache_path.is_absolute():
            base_dir = Path(__file__).resolve().parent.parent
            cache_path = base_dir / cache_path
        self.cache_dir: Path = cache_path
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create OCR cache directory {self.cache_dir}: {e}")

        self._model: Any = None
        self._processor: Any = None
        self.device: str = "cpu"
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()

    @property
    def is_available(self) -> bool:
        """OCR is always available via Baidu API or local fallback."""
        return True

    @property
    def is_baidu_active(self) -> bool:
        """Check if Baidu PaddleOCR should be used."""
        if self.provider == "baidu":
            return self.baidu_client.is_configured
        if self.provider == "auto":
            return self.baidu_client.is_configured
        return False

    def _ensure_model_loaded(self) -> None:
        """Lazy load local GOT-OCR model and processor as a singleton into memory."""
        if self._model is not None and self._processor is not None:
            return

        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        # Auto-detect GPU or use configured device
        if self.configured_device.lower() == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        elif self.configured_device.lower() == "cuda" and torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        logger.info(
            f"Loading local GOT-OCR 2.0 model ('{self.model_id}') on device '{self.device}'..."
        )

        try:
            self._processor = AutoProcessor.from_pretrained(self.model_id, local_files_only=True)
            self._model = AutoModelForImageTextToText.from_pretrained(
                self.model_id,
                low_cpu_mem_usage=True,
                dtype=torch.float16 if self.device == "cuda" else torch.float32,
                local_files_only=True,
            )
            self._model.to(self.device)
            self._model.eval()
            logger.info(f"Local GOT-OCR 2.0 model loaded from offline cache on {self.device}.")
        except Exception as local_err:
            logger.info(f"Offline cache check: {local_err}. Falling back to default loader...")
            try:
                self._processor = AutoProcessor.from_pretrained(self.model_id)
                self._model = AutoModelForImageTextToText.from_pretrained(
                    self.model_id,
                    low_cpu_mem_usage=True,
                    dtype=torch.float16 if self.device == "cuda" else torch.float32,
                )
                self._model.to(self.device)
                self._model.eval()
                logger.info(f"Local GOT-OCR 2.0 model loaded successfully on {self.device}.")
            except Exception as e:
                logger.error(f"Failed to load GOT-OCR 2.0 model '{self.model_id}': {e}")
                raise RuntimeError(f"Could not initialize local GOT-OCR 2.0: {e}") from e

    def _ocr_image_sync(self, pil_image: Image.Image) -> str:
        """Synchronous OCR inference executed inside threadpool for local GOT-OCR."""
        import torch

        self._ensure_model_loaded()

        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        inputs = self._processor(
            pil_image,
            return_tensors="pt",
            format=self.format_output,
        ).to(self.device)

        eos_ids = [151643, 151645]
        if hasattr(self._processor, "tokenizer"):
            tok = self._processor.tokenizer
            im_end_id = tok.convert_tokens_to_ids("<|im_end|>")
            if isinstance(im_end_id, int) and im_end_id > 0:
                eos_ids.append(im_end_id)
        eos_ids = list(set(eos_ids))

        with torch.no_grad():
            generate_ids = self._model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=self.max_tokens,
                eos_token_id=eos_ids,
                pad_token_id=151643,
            )

        output = self._processor.decode(
            generate_ids[0, inputs.input_ids.shape[1] :],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        ).strip()

        return output

    async def extract_document(
        self,
        file_input: bytes | str | Path,
        source_url: str | None = None,
        is_pdf: bool = True,
    ) -> tuple[str, list[ExtractedTable]]:
        """Extract high-fidelity Markdown and structured tables for an entire document.

        When Baidu PaddleOCR is active, processes the document as a single layout parsing job.
        Returns a tuple of (combined_markdown_text, extracted_tables).
        """
        if self.is_baidu_active:
            try:
                result = await self.baidu_client.process_document(
                    file_input=file_input,
                    source_url=source_url,
                    is_pdf=is_pdf,
                )
                return result.combined_markdown, result.tables
            except Exception as baidu_err:
                logger.warning(
                    f"Baidu PaddleOCR failed for document ({baidu_err}). Falling back to local OCR..."
                )

        return "", []

    async def extract_text_from_image(
        self,
        image_input: bytes | str | Path | Image.Image,
        page_number: int | None = None,
        doc_name: str | None = None,
    ) -> str:
        """Extract structured text and tables from an image or page bytes.

        Routes to Baidu PaddleOCR when enabled; falls back to local GOT-OCR 2.0.
        """
        if not image_input:
            return ""

        pil_image: Image.Image
        img_bytes: bytes
        cache_key: str = ""

        if isinstance(image_input, Image.Image):
            pil_image = image_input
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            cache_key = hashlib.sha256(img_bytes).hexdigest()
        elif isinstance(image_input, bytes):
            img_bytes = image_input
            cache_key = hashlib.sha256(img_bytes).hexdigest()
            pil_image = Image.open(io.BytesIO(img_bytes))
        elif isinstance(image_input, (str, Path)):
            path_str = str(image_input)
            with open(path_str, "rb") as f:
                img_bytes = f.read()
            cache_key = hashlib.sha256(img_bytes).hexdigest()
            pil_image = Image.open(io.BytesIO(img_bytes))
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        # 1. Check L1 Memory Cache
        if cache_key and cache_key in self._cache:
            return self._cache[cache_key]

        # 2. Check L2 Disk Cache
        if cache_key:
            cache_file = self.cache_dir / f"{cache_key}.txt"
            if cache_file.is_file():
                try:
                    cached_text = cache_file.read_text(encoding="utf-8")
                    self._cache[cache_key] = cached_text
                    logger.debug(f"OCR L2 disk cache hit for {cache_key[:12]}")
                    return cached_text
                except Exception as read_err:
                    logger.warning(f"Failed to read OCR cache file {cache_file}: {read_err}")

        # 3. Try Baidu PaddleOCR if active
        if self.is_baidu_active:
            try:
                baidu_res = await self.baidu_client.process_document(
                    file_input=img_bytes,
                    is_pdf=False,
                )
                extracted_text = baidu_res.combined_markdown
                if extracted_text:
                    self._cache[cache_key] = extracted_text
                    try:
                        cache_file = self.cache_dir / f"{cache_key}.txt"
                        cache_file.write_text(extracted_text, encoding="utf-8")
                    except Exception as write_err:
                        logger.warning(f"Failed to write OCR cache file: {write_err}")
                    return extracted_text
            except Exception as baidu_err:
                logger.warning(
                    f"Baidu PaddleOCR page error ({baidu_err}). Falling back to local GOT-OCR..."
                )

        # 4. Fallback to Local GOT-OCR 2.0
        page_info = f" (Page {page_number})" if page_number is not None else ""
        doc_info = f" for '{doc_name}'" if doc_name else ""
        logger.info(f"Running local GOT-OCR 2.0 on image{page_info}{doc_info}...")

        try:
            extracted_text = await asyncio.to_thread(self._ocr_image_sync, pil_image)
            if cache_key and extracted_text:
                self._cache[cache_key] = extracted_text
                try:
                    cache_file = self.cache_dir / f"{cache_key}.txt"
                    cache_file.write_text(extracted_text, encoding="utf-8")
                except Exception as write_err:
                    logger.warning(f"Failed to write OCR cache file: {write_err}")
            return extracted_text
        except Exception as e:
            logger.error(f"Error during local GOT-OCR 2.0 inference: {e}", exc_info=True)
            return ""


# Shared singleton instance
ocr_service = DocumentOCR()
