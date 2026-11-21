import logging
from typing import Any
from urllib.parse import urlparse

import httpx
import pymupdf as fitz

from ingestion.fetchers.base import BaseFetcher
from ingestion.ocr import ocr_service
from ingestion.schemas import ExtractedTable, FetchedDocument, SourceType

logger = logging.getLogger(__name__)


# Known mappings for ECAjmer departments and cells
KNOWN_DEPARTMENTS: dict[str, str] = {
    "cs-it": "Computer Science and Engineering",
    "cse": "Computer Science and Engineering",
    "it": "Information Technology",
    "ce": "Civil Engineering",
    "civil": "Civil Engineering",
    "ee": "Electrical Engineering",
    "electrical": "Electrical Engineering",
    "ece": "Electronics and Communication Engineering",
    "eic": "Electronic Instrumentation And Control Engineering",
    "me": "Mechanical Engineering",
    "mechanical": "Mechanical Engineering",
    "mca": "Computer Applications",
    "mba": "Management Studies",
    "physics": "Physics",
    "chemistry": "Chemistry",
    "maths": "Mathematics",
    "mathematics": "Mathematics",
    "english": "English",
    "humanities": "Humanities",
    "economy": "Economics",
    "economics": "Economics",
}

KNOWN_CELLS: dict[str, str] = {
    "registrar": "Registrar Section",
    "examination-section": "Examination Section",
    "exam-cell": "Examination Section",
    "exam": "Examination Section",
    "accounts": "Accounts Section",
    "accounts-section": "Accounts Section",
    "academic-section": "Academic Section",
    "academic": "Academic Section",
    "central-library": "Central Library",
    "library": "Central Library",
    "first-year": "First Year Cell",
    "first-year-cell": "First Year Cell",
    "tpo": "Training & Placement Cell",
    "placement-cell": "Training & Placement Cell",
    "hostels": "Hostels Cell",
    "hostel": "Hostels Cell",
    "proctor": "Proctor Section",
    "proctor-section": "Proctor Section",
    "grievance": "Grievance Cell",
    "women-cell": "Women Cell",
    "sc-st-cell": "SC ST Cell",
    "estate": "Estate Section",
    "sports": "Sports Section",
}


class ECAjmerFetcher(BaseFetcher):
    """Specialized fetcher for ecajmer.ac.in multi-department circulars, timetables, and PDF notices."""

    source_type: SourceType = "pdf"
    BASE_API_URL = "https://ecajmer.ac.in/api/circulars/public"

    def __init__(self, timeout: float = 30.0) -> None:
        super().__init__(timeout=timeout)

    @classmethod
    def parse_url(cls, url: str) -> tuple[str, int, str]:
        """Extracts (slug, category_id, department_name) from an ecajmer.ac.in URL.

        category_id: 1 for Circulars, 2 for Time Tables.
        """
        parsed = urlparse(url)
        path = parsed.path.strip("/").lower()
        parts = path.split("/")

        category_id = (
            2 if "timetable" in path or "time-table" in path or "timetables" in path else 1
        )

        # Check departments: departments/{slug}/...
        if "departments" in parts:
            idx = parts.index("departments")
            if idx + 1 < len(parts):
                slug = parts[idx + 1]
                dept_name = KNOWN_DEPARTMENTS.get(slug, slug.upper())
                return slug, category_id, dept_name

        # Check cells: ui/cells/{slug}/... or cells/{slug}/...
        if "cells" in parts:
            idx = parts.index("cells")
            if idx + 1 < len(parts):
                slug = parts[idx + 1]
                cell_name = KNOWN_CELLS.get(slug, slug.replace("-", " ").title())
                return slug, category_id, cell_name

        # Fallback: check if slug exists in KNOWN_DEPARTMENTS or KNOWN_CELLS
        for known_slug, dept_name in KNOWN_DEPARTMENTS.items():
            if known_slug in parts:
                return known_slug, category_id, dept_name

        for known_slug, cell_name in KNOWN_CELLS.items():
            if known_slug in parts:
                return known_slug, category_id, cell_name

        # Default fallback
        fallback_slug = parts[-1] if parts else "cs-it"
        return fallback_slug, category_id, fallback_slug.replace("-", " ").title()

    async def fetch_circular_entries(
        self,
        slug: str,
        category_id: int = 1,
        limit: int = 50,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch raw metadata list from the native ECAjmer API endpoint."""
        api_url = (
            f"{self.BASE_API_URL}/{slug}?page={page}&limit={limit}&mainCategoryId={category_id}"
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(api_url, headers=self.headers)
                if resp.status_code == 200:
                    payload = resp.json()
                    if isinstance(payload, dict) and payload.get("success"):
                        return payload.get("data", [])
                logger.warning(f"ECAjmer API returned status {resp.status_code} for {api_url}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch ECAjmer API circular entries from {api_url}: {e}")
            return []

    async def fetch_pdf_content(
        self,
        pdf_url: str,
        existing_hash: str | None = None,
        source_id: str | None = None,
        doc_name: str | None = None,
    ) -> tuple[bytes, str, list[ExtractedTable], int]:
        """Download a PDF file and extract plain text and tables using PyMuPDF.

        Fast-paths when existing_hash matches the downloaded binary hash, completely
        bypassing PyMuPDF parsing, rasterization, and OCR inference.
        """
        import hashlib

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(pdf_url, headers=self.headers)
                if resp.status_code != 200:
                    logger.warning(f"Failed to download PDF {pdf_url} (HTTP {resp.status_code})")
                    return b"", "", [], 0
                raw_bytes = resp.content
        except Exception as e:
            logger.warning(f"Error requesting PDF {pdf_url}: {e}")
            return b"", "", [], 0

        # Fast-path: Check binary hash against existing stored hash
        if existing_hash:
            doc_hash = hashlib.sha256(raw_bytes).hexdigest()
            if doc_hash == existing_hash:
                logger.info(
                    f"PDF binary hash matches existing record for {pdf_url.split('/')[-1]} - skipping OCR and extraction"
                )
                from ingestion.progress import progress_tracker

                fname = doc_name or pdf_url.split("/")[-1]
                progress_tracker.log(
                    f"Binary hash matched existing record for {fname}. Skipped OCR (zero overhead).",
                    level="bypass",
                    tag="HASH",
                    source_id=source_id,
                )
                return raw_bytes, "", [], 0

        page_texts: list[str] = []
        tables: list[ExtractedTable] = []
        page_count = 0

        try:
            with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
                page_count = len(doc)
                paddle_max_pages = getattr(ocr_service.settings, "BAIDU_OCR_MAX_PAGES", 100)

                # PaddleOCR-First Strategy:
                # If PaddleOCR-VL is configured and active, invoke it as the primary layout-aware
                # extractor for institutional notices and circulars.
                if ocr_service.is_baidu_active and page_count <= paddle_max_pages:
                    from ingestion.progress import progress_tracker

                    fname = doc_name or pdf_url.split("/")[-1]
                    progress_tracker.update_step(
                        phase="ocr_inference",
                        step_index=3,
                        current_action=f"Running PaddleOCR-VL (Primary) on circular: {fname}",
                        next_action="Parse layout, extract tables & markdown",
                        source_id=source_id,
                        log_message=f"Executing PaddleOCR-VL primary extractor on {fname} ({page_count} pages)",
                        log_level="ocr",
                        log_tag="OCR",
                    )
                    logger.info(
                        f"PaddleOCR-First: Processing circular PDF ({page_count} pages) via Baidu PaddleOCR-VL: {pdf_url}"
                    )
                    try:
                        batch_text, batch_tables = await ocr_service.extract_document(
                            file_input=raw_bytes,
                            source_url=pdf_url,
                            is_pdf=True,
                        )
                        if batch_text and batch_text.strip():
                            page_texts.append(batch_text)
                            tables.extend(batch_tables)
                            progress_tracker.log(
                                f"PaddleOCR-VL completed for {fname}: extracted {len(batch_tables)} tables, layout preserved",
                                level="ocr",
                                tag="OCR",
                                source_id=source_id,
                            )
                    except Exception as ocr_err:
                        logger.warning(
                            f"PaddleOCR primary extraction failed for {pdf_url} ({ocr_err}). Falling back to PyMuPDF..."
                        )

                if not page_texts:
                    for page_num in range(page_count):
                        page = doc[page_num]
                        text = str(page.get_text("text") or "").strip()

                        # Check for large embedded raster images (e.g. pasted screenshots of timetables)
                        has_large_image = False
                        try:
                            for img in page.get_images():
                                xref = img[0]
                                b_img = doc.extract_image(xref)
                                if (
                                    b_img
                                    and b_img.get("width", 0) >= 300
                                    and b_img.get("height", 0) >= 200
                                ):
                                    has_large_image = True
                                    break
                        except Exception:
                            pass

                        # If text density is sufficient and no suspicious table screenshots, use digital text
                        if len(text) >= ocr_service.min_text_threshold and not (
                            has_large_image and len(text) < 150
                        ):
                            page_texts.append(f"--- Page {page_num + 1} ---\n{text}")
                        else:
                            try:
                                pix = page.get_pixmap(dpi=ocr_service.dpi)
                                img_bytes = pix.tobytes("png")
                                ocr_text = await ocr_service.extract_text_from_image(
                                    img_bytes,
                                    page_number=page_num + 1,
                                    doc_name=pdf_url.split("/")[-1],
                                )
                                if ocr_text:
                                    page_texts.append(
                                        f"--- Page {page_num + 1} (OCR) ---\n{ocr_text}"
                                    )
                                elif text:
                                    page_texts.append(f"--- Page {page_num + 1} ---\n{text}")
                            except Exception as ocr_err:
                                logger.warning(
                                    f"OCR error on page {page_num + 1} of {pdf_url}: {ocr_err}"
                                )
                                if text:
                                    page_texts.append(f"--- Page {page_num + 1} ---\n{text}")

                        try:
                            tabs = page.find_tables()
                            if tabs and hasattr(tabs, "tables"):
                                for t_idx, tab in enumerate(tabs.tables):
                                    table_data = tab.extract()
                                    if table_data and len(table_data) > 0:
                                        headers = [str(c or "").strip() for c in table_data[0]]
                                        rows = [
                                            [str(c or "").strip() for c in row]
                                            for row in table_data[1:]
                                        ]
                                        tables.append(
                                            ExtractedTable(
                                                headers=headers,
                                                rows=rows,
                                                page_number=page_num + 1,
                                                title=f"Table {t_idx + 1} (Page {page_num + 1})",
                                            )
                                        )
                        except Exception:
                            pass
        except Exception as parse_err:
            logger.debug(f"PyMuPDF could not parse PDF bytes from {pdf_url}: {parse_err}")

        extracted_text = "\n\n".join(page_texts)
        if tables:
            table_md_blocks = [
                f"\n\n### Extracted Table ({t.title or f'Page {t.page_number}'})\n"
                + t.to_markdown()
                for t in tables
            ]
            extracted_text += "\n" + "\n".join(table_md_blocks)

        return raw_bytes, extracted_text, tables, page_count

    async def fetch_single_notice(
        self,
        entry: dict[str, Any],
        department_name: str,
        category_name: str = "Circular",
        existing_hash: str | None = None,
        source_id: str | None = None,
        item_index: int | None = None,
        total_items: int | None = None,
        slug: str | None = None,
    ) -> FetchedDocument:
        """Construct a full FetchedDocument from an individual circular entry and its attached PDF."""
        title = entry.get("title", "").strip()
        sno = entry.get("sno", "").strip()
        date = entry.get("date", "").strip()
        content_rel = entry.get("content", "").strip()

        # Build absolute PDF URL if present
        pdf_url = ""
        if content_rel:
            if content_rel.startswith("http://") or content_rel.startswith("https://"):
                pdf_url = content_rel
            else:
                clean_rel = content_rel.lstrip("/")
                pdf_url = f"https://ecajmer.ac.in/{clean_rel}"

        raw_bytes = b""
        pdf_text = ""
        tables: list[ExtractedTable] = []
        page_count = 0

        if pdf_url and pdf_url.lower().endswith(".pdf"):
            pdf_kwargs: dict[str, Any] = {"existing_hash": existing_hash}
            if source_id is not None:
                pdf_kwargs["source_id"] = source_id
                pdf_kwargs["doc_name"] = title or pdf_url.split("/")[-1]
            raw_bytes, pdf_text, tables, page_count = await self.fetch_pdf_content(
                pdf_url,
                **pdf_kwargs,
            )

        # Fallback raw_bytes if empty
        if not raw_bytes:
            raw_bytes = f"{title}\n{sno}\n{date}\n{pdf_url}".encode()

        # Compile structured header markdown
        header_blocks = [
            f"# {title}",
            f"**Notice S.No:** {sno}" if sno else "",
            f"**Date:** {date}" if date else "",
            f"**Department/Section:** {department_name}",
            f"**Category:** {category_name}",
            f"**Official Attachment URL:** {pdf_url}" if pdf_url else "",
        ]
        full_text = "\n".join(filter(None, header_blocks))
        if pdf_text:
            full_text += f"\n\n## Attached Notice Document Content\n{pdf_text}"

        source_doc_url = (
            pdf_url if pdf_url else f"https://www.ecajmer.ac.in/notice/{sno or entry.get('id')}"
        )

        metadata = {
            "title": title,
            "sno": sno,
            "date": date,
            "posted_date": date,
            "portal_id": entry.get("id"),
            "id": entry.get("id"),
            "department": department_name,
            "source_section": department_name,
            "category": category_name,
            "section_slug": slug,
            "pdf_url": pdf_url,
            "page_count": page_count,
            "table_count": len(tables),
            "created_at": entry.get("createdAt"),
        }

        return FetchedDocument(
            source_url=source_doc_url,
            source_type="pdf" if pdf_url.lower().endswith(".pdf") else "html",
            raw_content=raw_bytes,
            extracted_text=full_text,
            tables=tables,
            metadata=metadata,
        )

    async def fetch_all_source_documents(
        self,
        source_url: str,
        limit: int = 50,
        department: str | None = None,
        existing_hashes: dict[str, str] | None = None,
        source_id: str | None = None,
    ) -> list[FetchedDocument]:
        """Fetch all circulars / timetable documents for a given source link up to the specified limit (e.g. 50 or 20)."""
        slug, category_id, detected_dept = self.parse_url(source_url)
        dept_name = department or detected_dept
        category_name = "Time Table" if category_id == 2 else "Circular"

        from ingestion.progress import progress_tracker

        progress_tracker.update_step(
            phase="portal_fetch",
            step_index=1,
            current_action=f"Connecting to portal API: {slug} ({category_name})",
            next_action=f"Retrieve up to {limit} circular entries",
            source_id=source_id,
            log_message=f"Querying portal API endpoint for '{slug}' (limit={limit})",
            log_level="fetch",
            log_tag="PORTAL",
        )

        entries = await self.fetch_circular_entries(
            slug=slug,
            category_id=category_id,
            limit=limit,
            page=1,
        )

        total_entries = len(entries)
        logger.info(f"Retrieved {total_entries} notice entries for {source_url} (limit={limit})")

        progress_tracker.update_step(
            phase="portal_fetch",
            step_index=1,
            current_action=f"Discovered {total_entries} notices from portal. Inspecting attachments...",
            next_action="Download notices and verify SHA-256 content hashes",
            source_id=source_id,
            log_message=f"Retrieved {total_entries} structured notice entries from portal",
            log_level="info",
            log_tag="PORTAL",
            stats_update={"total": total_entries},
        )

        documents: list[FetchedDocument] = []
        bypassed_count = 0

        for idx, entry in enumerate(entries, start=1):
            try:
                # Pre-determine PDF URL to check against existing_hashes
                content_rel = entry.get("content", "").strip()
                title = entry.get("title", "").strip()
                sno = entry.get("sno", "").strip()
                pdf_url = ""
                if content_rel:
                    if content_rel.startswith("http://") or content_rel.startswith("https://"):
                        pdf_url = content_rel
                    else:
                        clean_rel = content_rel.lstrip("/")
                        pdf_url = f"https://ecajmer.ac.in/{clean_rel}"

                entry_hash = existing_hashes.get(pdf_url) if (existing_hashes and pdf_url) else None
                fname = (
                    pdf_url.split("/")[-1]
                    if pdf_url
                    else (f"notice_{sno}.html" if sno else f"notice_{idx}.html")
                )

                progress_tracker.update_step(
                    phase="pdf_download",
                    step_index=2,
                    current_action=f"[{idx}/{total_entries}] Inspecting notice: {title[:60] or fname}",
                    next_action="Verify SHA-256 hash against existing records",
                    source_id=source_id,
                    active_document={
                        "title": title or fname,
                        "filename": fname,
                        "url": pdf_url,
                        "source_type": "pdf" if pdf_url.lower().endswith(".pdf") else "html",
                    },
                    stats_update={"checked": idx - 1},
                )

                doc = await self.fetch_single_notice(
                    entry=entry,
                    department_name=dept_name,
                    category_name=category_name,
                    existing_hash=entry_hash,
                    source_id=source_id,
                    item_index=idx,
                    total_items=total_entries,
                    slug=slug,
                )

                if entry_hash and doc.extracted_text == "":
                    bypassed_count += 1

                progress_tracker.update_step(
                    phase="hash_check",
                    step_index=2,
                    current_action=f"[{idx}/{total_entries}] Verified {fname}",
                    next_action=(
                        f"Inspect next notice in queue ({idx+1}/{total_entries})"
                        if idx < total_entries
                        else "Commence semantic chunking & vector embedding"
                    ),
                    source_id=source_id,
                    stats_update={
                        "checked": idx,
                        "bypassed_count": bypassed_count,
                    },
                )

                documents.append(doc)
            except Exception as item_err:
                logger.warning(f"Error fetching notice {entry.get('sno')}: {item_err}")
                progress_tracker.log(
                    f"Warning: Failed to fetch notice {entry.get('sno')}: {item_err}",
                    level="warn",
                    tag="WARN",
                    source_id=source_id,
                )

        return documents

    async def fetch(self, source: str, **kwargs: Any) -> FetchedDocument:
        """Fetch implementation satisfying BaseFetcher interface (fetches the latest document from source)."""
        docs = await self.fetch_all_source_documents(
            source_url=source,
            limit=kwargs.get("limit", 1),
            department=kwargs.get("department"),
            existing_hashes=kwargs.get("existing_hashes"),
            source_id=kwargs.get("source_id"),
        )
        if docs:
            return docs[0]

        # Fallback dummy fetched document
        return FetchedDocument(
            source_url=source,
            source_type="html",
            raw_content=b"No documents found",
            extracted_text="No documents found on ECAjmer portal.",
            tables=[],
            metadata={"title": "ECAjmer Document"},
        )
