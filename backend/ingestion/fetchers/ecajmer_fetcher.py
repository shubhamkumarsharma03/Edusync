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
    "ce": "Civil Engineering",
    "ee": "Electrical Engineering",
    "ece": "Electronics and Communication Engineering",
    "eic": "Electronic Instrumentation And Control Engineering",
    "me": "Mechanical Engineering",
    "mca": "Computer Applications",
    "mba": "Management Studies",
    "physics": "Physics",
    "chemistry": "Chemistry",
    "maths": "Mathematics",
    "english": "English",
    "economy": "Economics",
}

KNOWN_CELLS: dict[str, str] = {
    "registrar": "Registrar Section",
    "examination-section": "Examination Section",
    "accounts": "Accounts Section",
    "academic-section": "Academic Section",
    "central-library": "Central Library",
    "first-year": "First Year Cell",
    "tpo": "Training & Placement Cell",
    "hostels": "Hostels Cell",
    "proctor": "Proctor Section",
    "grievance": "Grievance Cell",
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

    async def fetch_pdf_content(self, pdf_url: str) -> tuple[bytes, str, list[ExtractedTable], int]:
        """Download a PDF file and extract plain text and tables using PyMuPDF."""
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

        page_texts: list[str] = []
        tables: list[ExtractedTable] = []
        page_count = 0

        try:
            with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
                page_count = len(doc)
                for page_num in range(page_count):
                    page = doc[page_num]
                    text = page.get_text("text").strip()
                    if len(text) >= ocr_service.min_text_threshold:
                        page_texts.append(f"--- Page {page_num + 1} ---\n{text}")
                    else:
                        # Scanned image page -> Convert page to image and run local GOT-OCR 2.0
                        try:
                            pix = page.get_pixmap(dpi=ocr_service.dpi)
                            img_bytes = pix.tobytes("png")
                            ocr_text = await ocr_service.extract_text_from_image(
                                img_bytes,
                                page_number=page_num + 1,
                                doc_name=pdf_url.split("/")[-1],
                            )
                            if ocr_text:
                                page_texts.append(f"--- Page {page_num + 1} (GOT-OCR) ---\n{ocr_text}")
                            elif text:
                                page_texts.append(f"--- Page {page_num + 1} ---\n{text}")
                        except Exception as ocr_err:
                            logger.warning(
                                f"Local GOT-OCR error on page {page_num + 1} of {pdf_url}: {ocr_err}"
                            )
                            if text:
                                page_texts.append(f"--- Page {page_num + 1} ---\n{text}")

                    try:
                        tabs = page.find_tables()
                        for t_idx, tab in enumerate(tabs):
                            table_data = tab.extract()
                            if table_data and len(table_data) > 0:
                                headers = [str(c or "").strip() for c in table_data[0]]
                                rows = [
                                    [str(c or "").strip() for c in row] for row in table_data[1:]
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
            raw_bytes, pdf_text, tables, page_count = await self.fetch_pdf_content(pdf_url)

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
            "department": department_name,
            "category": category_name,
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
    ) -> list[FetchedDocument]:
        """Fetch all circulars / timetable documents for a given source link up to the specified limit (e.g. 50 or 20)."""
        slug, category_id, detected_dept = self.parse_url(source_url)
        dept_name = department or detected_dept
        category_name = "Time Table" if category_id == 2 else "Circular"

        entries = await self.fetch_circular_entries(
            slug=slug,
            category_id=category_id,
            limit=limit,
            page=1,
        )

        logger.info(f"Retrieved {len(entries)} notice entries for {source_url} (limit={limit})")

        documents: list[FetchedDocument] = []
        for entry in entries:
            try:
                doc = await self.fetch_single_notice(
                    entry=entry,
                    department_name=dept_name,
                    category_name=category_name,
                )
                documents.append(doc)
            except Exception as item_err:
                logger.warning(f"Error fetching notice {entry.get('sno')}: {item_err}")

        return documents

    async def fetch(self, source: str, **kwargs: Any) -> FetchedDocument:
        """Fetch implementation satisfying BaseFetcher interface (fetches the latest document from source)."""
        docs = await self.fetch_all_source_documents(
            source_url=source,
            limit=kwargs.get("limit", 1),
            department=kwargs.get("department"),
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
