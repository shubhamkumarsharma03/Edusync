import logging
from typing import Any

import pymupdf as fitz

from ingestion.fetchers.base import BaseFetcher
from ingestion.ocr import ocr_service
from ingestion.schemas import ExtractedTable, FetchedDocument, SourceType

logger = logging.getLogger(__name__)


class PDFFetcher(BaseFetcher):
    """Fetcher for PDF documents using PyMuPDF (fitz) with local GOT-OCR 2.0 fallback."""

    source_type: SourceType = "pdf"

    async def fetch(self, source: str, **kwargs: Any) -> FetchedDocument:
        """Fetch a PDF document from URL or local path and extract text + tables.

        Fast-paths when existing_hash matches the downloaded binary hash, completely
        bypassing PyMuPDF parsing, rasterization, and OCR inference.
        """
        import hashlib

        raw_bytes, base_meta = await self._get_raw_bytes(source)

        existing_hash = kwargs.get("existing_hash")
        if existing_hash and hashlib.sha256(raw_bytes).hexdigest() == existing_hash:
            logger.info(f"PDF content hash matches existing record for {source} - skipping OCR")
            return FetchedDocument(
                source_url=source,
                source_type="pdf",
                raw_content=raw_bytes,
                extracted_text="",
                tables=[],
                metadata=base_meta,
            )

        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception as e:
            logger.error(f"Failed to open PDF from {source}: {e}")
            raise ValueError(f"Invalid or corrupted PDF document from {source}: {e}") from e

        page_texts: list[str] = []
        tables: list[ExtractedTable] = []
        max_ocr = kwargs.get("max_ocr_pages")
        if max_ocr is None:
            max_ocr = getattr(ocr_service, "max_pages_per_doc", 5)
        ocr_pages_done = 0

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text").strip()
                if len(text) >= ocr_service.min_text_threshold:
                    page_texts.append(f"--- Page {page_num + 1} ---\n{text}")
                elif ocr_pages_done < max_ocr:
                    try:
                        pix = page.get_pixmap(dpi=ocr_service.dpi)
                        img_bytes = pix.tobytes("png")
                        ocr_text = await ocr_service.extract_text_from_image(
                            img_bytes,
                            page_number=page_num + 1,
                            doc_name=source.split("/")[-1].split("\\")[-1],
                        )
                        ocr_pages_done += 1
                        if ocr_text:
                            page_texts.append(f"--- Page {page_num + 1} (GOT-OCR) ---\n{ocr_text}")
                        elif text:
                            page_texts.append(f"--- Page {page_num + 1} ---\n{text}")
                    except Exception as ocr_err:
                        logger.warning(
                            f"Local GOT-OCR error on page {page_num + 1} of {source}: {ocr_err}"
                        )
                        if text:
                            page_texts.append(f"--- Page {page_num + 1} ---\n{text}")
                else:
                    logger.info(
                        f"Skipping OCR on page {page_num + 1} of {source.split('/')[-1]} (reached max OCR limit: {max_ocr})"
                    )
                    if text:
                        page_texts.append(f"--- Page {page_num + 1} ---\n{text}")

                # Extract structured tables using PyMuPDF table finder
                try:
                    tabs = page.find_tables()
                    for t_idx, tab in enumerate(tabs):
                        table_data = tab.extract()
                        if table_data and len(table_data) > 0:
                            headers = [str(c or "").strip() for c in table_data[0]]
                            rows = [[str(c or "").strip() for c in row] for row in table_data[1:]]
                            extracted_table = ExtractedTable(
                                headers=headers,
                                rows=rows,
                                page_number=page_num + 1,
                                title=f"Table {t_idx + 1} (Page {page_num + 1})",
                            )
                            tables.append(extracted_table)
                except Exception as tab_err:
                    logger.debug(f"Table extraction skipped on page {page_num + 1}: {tab_err}")

            doc_metadata = doc.metadata or {}
            metadata: dict[str, Any] = {
                **base_meta,
                "title": doc_metadata.get("title") or kwargs.get("title", ""),
                "author": doc_metadata.get("author", ""),
                "page_count": len(doc),
                "format": doc_metadata.get("format", "PDF"),
                "table_count": len(tables),
            }

            extracted_text = "\n\n".join(page_texts)

            # If tables were extracted, append their markdown representations to extracted_text for completeness
            if tables:
                table_md_blocks = [
                    f"\n\n### Extracted Table ({t.title or f'Page {t.page_number}'})\n"
                    + t.to_markdown()
                    for t in tables
                ]
                extracted_text += "\n" + "\n".join(table_md_blocks)

            return FetchedDocument(
                source_url=source,
                source_type=self.source_type,
                raw_content=raw_bytes,
                extracted_text=extracted_text,
                tables=tables,
                metadata=metadata,
            )
        finally:
            doc.close()


async def fetch_pdf(source: str, timeout: float = 30.0, **kwargs: Any) -> FetchedDocument:
    """Convenience helper to fetch a PDF document."""
    fetcher = PDFFetcher(timeout=timeout)
    return await fetcher.fetch(source, **kwargs)
