from ingestion.fetchers.base import BaseFetcher
from ingestion.fetchers.factory import detect_source_type, fetch_document, get_fetcher
from ingestion.fetchers.html_fetcher import HTMLFetcher, fetch_html
from ingestion.fetchers.pdf_fetcher import PDFFetcher, fetch_pdf
from ingestion.fetchers.sheet_fetcher import SheetFetcher, fetch_sheet

__all__ = [
    "BaseFetcher",
    "PDFFetcher",
    "HTMLFetcher",
    "SheetFetcher",
    "fetch_pdf",
    "fetch_html",
    "fetch_sheet",
    "fetch_document",
    "get_fetcher",
    "detect_source_type",
]
