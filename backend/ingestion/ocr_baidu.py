import asyncio
import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from api.config import get_settings
from ingestion.schemas import ExtractedTable
from ingestion.table_extractor import parse_markdown_tables

logger = logging.getLogger(__name__)


class BaiduOCRPageResult(BaseModel):
    """Extracted OCR result for a single document page."""

    page_number: int
    markdown_text: str
    tables: list[ExtractedTable] = Field(default_factory=list)
    image_urls: dict[str, str] = Field(default_factory=dict)


class BaiduOCRDocumentResult(BaseModel):
    """Complete multi-page OCR result for a document."""

    source_hash: str
    total_pages: int
    combined_markdown: str
    pages: list[BaiduOCRPageResult] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)


class BaiduPaddleOCRClient:
    """Client for Baidu AI Studio PaddleOCR APIs.

    Supports:
    1. PaddleOCR-VL-1.6 Async Job API: multi-page layout parsing with native Markdown and tables.
    2. Direct Serving Inference API: synchronous POST /ocr with Base64 payloads and fileType flags.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_url: str = getattr(
            self.settings,
            "BAIDU_OCR_API_URL",
            "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs",
        )
        self.token: str | None = getattr(self.settings, "BAIDU_OCR_TOKEN", None) or getattr(
            self.settings, "PADDLEOCR_TOKEN", None
        )
        self.model: str = getattr(self.settings, "BAIDU_OCR_MODEL", "PaddleOCR-VL-1.6")
        self.mode: str = getattr(self.settings, "BAIDU_OCR_MODE", "auto").lower()
        self.poll_interval: float = float(getattr(self.settings, "BAIDU_OCR_POLL_INTERVAL", 3.0))
        self.timeout: float = float(getattr(self.settings, "BAIDU_OCR_TIMEOUT", 120.0))
        self.use_orientation: bool = bool(
            getattr(self.settings, "BAIDU_OCR_USE_DOC_ORIENTATION", True)
        )
        self.use_unwarping: bool = bool(getattr(self.settings, "BAIDU_OCR_USE_DOC_UNWARPING", True))
        self.use_textline_orientation: bool = bool(
            getattr(self.settings, "BAIDU_OCR_USE_TEXTLINE_ORIENTATION", False)
        )
        self.use_chart_recognition: bool = bool(
            getattr(self.settings, "BAIDU_OCR_USE_CHART_RECOGNITION", False)
        )
        self.visualize: bool = bool(getattr(self.settings, "BAIDU_OCR_VISUALIZE", False))

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

        # L1 Memory Cache: sha256 -> BaiduOCRDocumentResult
        self._cache: dict[str, BaiduOCRDocumentResult] = {}
        self._lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        """Check if a valid Baidu AI Studio token is configured."""
        return bool(self.token and self.token.strip())

    def _determine_protocol(self) -> Literal["async_job", "serving"]:
        """Determine whether to use Async Job protocol or Direct Serving protocol."""
        if self.mode == "async_job":
            return "async_job"
        if self.mode == "serving":
            return "serving"

        # Auto detection based on URL
        if "/jobs" in self.api_url.lower():
            return "async_job"
        return "serving"

    def _build_auth_headers(self, protocol: str) -> dict[str, str]:
        """Build authorization headers for the given protocol."""
        if not self.token:
            return {}
        token = self.token.strip()
        # For Async Jobs, authorization header is typically "bearer <token>"
        # For Direct Serving API, authorization header is typically "token <token>"
        if protocol == "async_job":
            auth_val = f"bearer {token}" if not token.lower().startswith("bearer ") else token
        else:
            auth_val = f"token {token}" if not token.lower().startswith("token ") else token

        return {"Authorization": auth_val}

    async def process_document(
        self,
        file_input: bytes | str | Path,
        source_url: str | None = None,
        is_pdf: bool = True,
        force_refresh: bool = False,
    ) -> BaiduOCRDocumentResult:
        """Primary entrypoint to run OCR on a document (PDF or image).

        Handles L1/L2 caching, auto-protocol selection, and table extraction.
        """
        if not self.is_configured:
            raise ValueError("Baidu PaddleOCR token is not configured.")

        # Resolve raw bytes and compute cache key
        raw_bytes: bytes
        input_url: str | None = None

        if isinstance(file_input, bytes):
            raw_bytes = file_input
        elif isinstance(file_input, (str, Path)):
            str_path = str(file_input)
            if str_path.startswith("http://") or str_path.startswith("https://"):
                input_url = str_path
                # Fetch remote bytes to compute hash for caching
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(input_url)
                    resp.raise_for_status()
                    raw_bytes = resp.content
            else:
                p = Path(str_path)
                raw_bytes = p.read_bytes()
        else:
            raise ValueError(f"Unsupported input type for OCR: {type(file_input)}")

        cache_key = hashlib.sha256(raw_bytes).hexdigest()

        # Check L1 memory cache
        if not force_refresh and cache_key in self._cache:
            logger.debug(f"Baidu OCR L1 cache hit for {cache_key[:12]}")
            return self._cache[cache_key]

        # Check L2 disk cache
        cache_file = self.cache_dir / f"baidu_{cache_key}.json"
        if not force_refresh and cache_file.is_file():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                result = BaiduOCRDocumentResult.model_validate(cached_data)
                self._cache[cache_key] = result
                logger.debug(f"Baidu OCR L2 disk cache hit for {cache_key[:12]}")
                return result
            except Exception as read_err:
                logger.warning(f"Failed to read OCR cache file {cache_file}: {read_err}")

        # Execute OCR based on protocol
        protocol = self._determine_protocol()
        logger.info(
            f"Invoking Baidu PaddleOCR (protocol='{protocol}', model='{self.model}') for doc {cache_key[:12]}..."
        )

        async with self._lock:
            if protocol == "async_job":
                result = await self._process_async_job(
                    raw_bytes=raw_bytes,
                    input_url=input_url or source_url,
                    cache_key=cache_key,
                    is_pdf=is_pdf,
                )
            else:
                result = await self._process_serving_inference(
                    raw_bytes=raw_bytes,
                    cache_key=cache_key,
                    is_pdf=is_pdf,
                )

            # Store in caches
            self._cache[cache_key] = result
            try:
                cache_file.write_text(
                    result.model_dump_json(indent=2),
                    encoding="utf-8",
                )
            except Exception as write_err:
                logger.warning(f"Failed to write Baidu OCR disk cache file: {write_err}")

            return result

    async def _extract_json(self, resp: Any) -> dict[str, Any]:
        """Safely extract json from httpx response, handling async mocks if present."""
        raw_json = resp.json()
        if asyncio.iscoroutine(raw_json):
            return await raw_json
        return raw_json

    async def _process_async_job(
        self,
        raw_bytes: bytes,
        input_url: str | None,
        cache_key: str,
        is_pdf: bool,
    ) -> BaiduOCRDocumentResult:
        """Submit and poll Baidu AI Studio PaddleOCR-VL async job."""
        headers = self._build_auth_headers("async_job")
        optional_payload = {
            "useDocOrientationClassify": self.use_orientation,
            "useDocUnwarping": self.use_unwarping,
            "useChartRecognition": self.use_chart_recognition,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 1. Job submission
            if input_url and input_url.startswith("http"):
                # URL Mode
                headers["Content-Type"] = "application/json"
                payload = {
                    "fileUrl": input_url,
                    "model": self.model,
                    "optionalPayload": optional_payload,
                }
                job_resp = await client.post(self.api_url, json=payload, headers=headers)
            else:
                # File upload mode
                ext = ".pdf" if is_pdf else ".png"
                files = {
                    "file": (
                        f"document_{cache_key[:8]}{ext}",
                        raw_bytes,
                        "application/octet-stream",
                    )
                }
                data = {
                    "model": self.model,
                    "optionalPayload": json.dumps(optional_payload),
                }
                job_resp = await client.post(self.api_url, headers=headers, data=data, files=files)

            if job_resp.status_code != 200:
                logger.error(
                    f"Baidu OCR job submission failed [{job_resp.status_code}]: {job_resp.text}"
                )
                raise RuntimeError(
                    f"Baidu OCR submission failed ({job_resp.status_code}): {job_resp.text}"
                )

            resp_json = await self._extract_json(job_resp)
            job_data = resp_json.get("data", {})
            job_id = job_data.get("jobId")
            if not job_id:
                raise RuntimeError(f"No jobId returned from Baidu OCR: {resp_json}")

            logger.info(
                f"Baidu OCR job submitted successfully (jobId={job_id}). Polling for results..."
            )

            # 2. Polling loop
            poll_url = f"{self.api_url.rstrip('/')}/{job_id}"
            poll_headers = self._build_auth_headers("async_job")
            start_time = asyncio.get_event_loop().time()
            jsonl_url: str = ""

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > self.timeout:
                    raise TimeoutError(f"Baidu OCR job {job_id} timed out after {elapsed:.1f}s")

                status_resp = await client.get(poll_url, headers=poll_headers)
                if status_resp.status_code != 200:
                    raise RuntimeError(
                        f"Failed to poll Baidu OCR job {job_id}: {status_resp.status_code} {status_resp.text}"
                    )

                status_json = await self._extract_json(status_resp)
                status_data = status_json.get("data", {})
                state = status_data.get("state")

                if state == "done":
                    result_url_obj = status_data.get("resultUrl", {})
                    jsonl_url = result_url_obj.get("jsonUrl", "")
                    logger.info(f"Baidu OCR job {job_id} finished successfully.")
                    break
                elif state == "failed":
                    err_msg = status_data.get("errorMsg", "Unknown failure")
                    raise RuntimeError(f"Baidu OCR job {job_id} failed: {err_msg}")
                elif state in ("pending", "running"):
                    progress = status_data.get("extractProgress", {})
                    extracted = progress.get("extractedPages", 0)
                    total = progress.get("totalPages", 0)
                    logger.debug(
                        f"Baidu OCR job {job_id} state={state} ({extracted}/{total} pages)"
                    )
                else:
                    logger.debug(f"Baidu OCR job {job_id} state={state}")

                await asyncio.sleep(self.poll_interval)

            if not jsonl_url:
                raise RuntimeError(f"Baidu OCR job {job_id} completed but returned no jsonUrl")

            # 3. Download & parse JSONL results
            jsonl_resp = await client.get(jsonl_url)
            jsonl_resp.raise_for_status()

            return self._parse_jsonl_content(jsonl_resp.text, cache_key=cache_key)

    def _parse_jsonl_content(self, jsonl_text: str, cache_key: str) -> BaiduOCRDocumentResult:
        """Parse JSONL lines into structured pages and markdown tables."""
        pages: list[BaiduOCRPageResult] = []
        all_tables: list[ExtractedTable] = []
        page_mds: list[str] = []

        lines = jsonl_text.strip().splitlines()
        page_idx = 1

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            try:
                line_obj = json.loads(line_str)
                result_obj = line_obj.get("result", {})
                layout_results = result_obj.get("layoutParsingResults", [])

                for res in layout_results:
                    md_obj = res.get("markdown", {})
                    page_text = md_obj.get("text", "").strip()
                    images = md_obj.get("images", {})

                    # Extract markdown tables from this page
                    page_tables = parse_markdown_tables(page_text, page_number=page_idx)
                    all_tables.extend(page_tables)

                    page_res = BaiduOCRPageResult(
                        page_number=page_idx,
                        markdown_text=page_text,
                        tables=page_tables,
                        image_urls=images,
                    )
                    pages.append(page_res)
                    page_mds.append(f"--- Page {page_idx} (Baidu PaddleOCR) ---\n{page_text}")
                    page_idx += 1
            except Exception as parse_err:
                logger.warning(f"Error parsing line from Baidu OCR JSONL: {parse_err}")

        combined_md = "\n\n".join(page_mds)
        return BaiduOCRDocumentResult(
            source_hash=cache_key,
            total_pages=len(pages),
            combined_markdown=combined_md,
            pages=pages,
            tables=all_tables,
        )

    async def _process_serving_inference(
        self,
        raw_bytes: bytes,
        cache_key: str,
        is_pdf: bool,
    ) -> BaiduOCRDocumentResult:
        """Direct synchronous serving call (POST /ocr) with Base64 payload."""
        headers = self._build_auth_headers("serving")
        headers["Content-Type"] = "application/json"

        file_b64 = base64.b64encode(raw_bytes).decode("ascii")
        file_type = 0 if is_pdf else 1

        payload = {
            "file": file_b64,
            "fileType": file_type,
            "useDocOrientationClassify": self.use_orientation,
            "useDocUnwarping": self.use_unwarping,
            "useTextlineOrientation": self.use_textline_orientation,
            "visualize": self.visualize,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.api_url, json=payload, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Baidu OCR serving request failed ({resp.status_code}): {resp.text}"
                )

            resp_json = await self._extract_json(resp)
            error_code = resp_json.get("errorCode", 0)
            if error_code != 0:
                err_msg = resp_json.get("errorMsg", "Serving inference error")
                raise RuntimeError(f"Baidu OCR serving error {error_code}: {err_msg}")

            result_obj = resp_json.get("result", {})
            ocr_results = result_obj.get("ocrResults", [])

            pages: list[BaiduOCRPageResult] = []
            all_tables: list[ExtractedTable] = []
            page_mds: list[str] = []

            for idx, res in enumerate(ocr_results):
                page_num = idx + 1
                page_text = self._extract_text_from_serving_result(res)
                page_tables = parse_markdown_tables(page_text, page_number=page_num)
                all_tables.extend(page_tables)

                pages.append(
                    BaiduOCRPageResult(
                        page_number=page_num,
                        markdown_text=page_text,
                        tables=page_tables,
                    )
                )
                page_mds.append(f"--- Page {page_num} (Baidu PaddleOCR) ---\n{page_text}")

            combined_md = "\n\n".join(page_mds)
            return BaiduOCRDocumentResult(
                source_hash=cache_key,
                total_pages=len(pages),
                combined_markdown=combined_md,
                pages=pages,
                tables=all_tables,
            )

    def _extract_text_from_serving_result(self, res: dict[str, Any]) -> str:
        """Extract legible text or markdown from a serving result entry."""
        pruned = res.get("prunedResult")
        if isinstance(pruned, str):
            return pruned

        if isinstance(pruned, dict):
            # Check for markdown field
            if "markdown" in pruned and isinstance(pruned["markdown"], dict):
                return str(pruned["markdown"].get("text", "")).strip()

            # Check for texts, words, or rec_text lists
            for text_key in ("texts", "rec_texts", "words", "lines"):
                if text_key in pruned and isinstance(pruned[text_key], list):
                    return "\n".join(str(item) for item in pruned[text_key] if item)

            # Check for layout / blocks
            if "layout" in pruned and isinstance(pruned["layout"], list):
                lines: list[str] = []
                for item in pruned["layout"]:
                    if isinstance(item, dict) and "text" in item:
                        lines.append(str(item["text"]))
                    elif isinstance(item, str):
                        lines.append(item)
                if lines:
                    return "\n".join(lines)

            # Fallback to stringified prunedResult
            return json.dumps(pruned, ensure_ascii=False)

        # Fallback if pruned is a list
        if isinstance(pruned, list):
            return "\n".join(str(p) for p in pruned)

        return ""


# Shared singleton client
baidu_ocr_client = BaiduPaddleOCRClient()
