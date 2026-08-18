from typing import Any
from urllib.parse import urlparse

from ingestion.fetchers.base import BaseFetcher
from ingestion.fetchers.html_fetcher import HTMLFetcher
from ingestion.fetchers.pdf_fetcher import PDFFetcher
from ingestion.fetchers.sheet_fetcher import SheetFetcher
from ingestion.schemas import FetchedDocument, SourceType


def detect_source_type(source: str) -> SourceType:
    """Detect source type based on URL extension or file path."""
    parsed = urlparse(source)
    path = parsed.path.lower() if parsed.path else source.lower()

    if path.endswith(".pdf"):
        return "pdf"
    elif path.endswith(".csv") or path.endswith(".tsv") or path.endswith(".xlsx"):
        return "sheet"
    elif path.endswith(".html") or path.endswith(".htm") or parsed.scheme in ("http", "https"):
        return "html"
    return "pdf"  # Default fallback for document links


def get_fetcher(
    source: str,
    source_type: SourceType | None = None,
    timeout: float = 30.0,
    **kwargs: Any,
) -> BaseFetcher:
    """Instantiate appropriate fetcher for a given source and type."""
    detected_type = source_type or detect_source_type(source)

    if detected_type == "pdf":
        return PDFFetcher(timeout=timeout)
    elif detected_type == "html":
        use_playwright = kwargs.get("use_playwright", False)
        return HTMLFetcher(timeout=timeout, use_playwright=use_playwright)
    elif detected_type == "sheet":
        return SheetFetcher(timeout=timeout)
    else:
        raise ValueError(f"Unsupported source type: {detected_type}")


async def fetch_document(
    source: str,
    source_type: SourceType | None = None,
    **kwargs: Any,
) -> FetchedDocument:
    """Unified entry point to fetch and parse any supported document source."""
    fetcher = get_fetcher(source, source_type=source_type, **kwargs)
    return await fetcher.fetch(source, **kwargs)
