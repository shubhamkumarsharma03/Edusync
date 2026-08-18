import logging
from typing import Any

import pymupdf as fitz

from ingestion.fetchers.base import BaseFetcher
from ingestion.schemas import ExtractedTable, FetchedDocument, SourceType

logger = logging.getLogger(__name__)


class PDFFetcher(BaseFetcher):
    """Fetcher for PDF documents using PyMuPDF (fitz)."""

    source_type: SourceType = "pdf"

    async def fetch(self, source: str, **kwargs: Any) -> FetchedDocument:
        """Fetch a PDF document from URL or local path and extract text + tables."""
        raw_bytes, base_meta = await self._get_raw_bytes(source)

        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception as e:
            logger.error(f"Failed to open PDF from {source}: {e}")
            raise ValueError(f"Invalid or corrupted PDF document from {source}: {e}") from e

        page_texts: list[str] = []
        tables: list[ExtractedTable] = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text").strip()
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
