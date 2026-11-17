import logging
import os
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ingestion.fetchers.base import BaseFetcher
from ingestion.schemas import ExtractedTable, FetchedDocument, SourceType

logger = logging.getLogger(__name__)


class HTMLFetcher(BaseFetcher):
    """Fetcher for HTML documents supporting static BS4 parsing and dynamic Playwright rendering."""

    source_type: SourceType = "html"

    def __init__(self, timeout: float = 30.0, use_playwright: bool = False) -> None:
        super().__init__(timeout=timeout)
        self.use_playwright = use_playwright

    async def _fetch_dynamic_html(self, url: str) -> tuple[str, bytes]:
        """Fetch HTML content using headless Playwright for JS-rendered SPAs."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(user_agent=self.headers["User-Agent"])
                await page.goto(
                    url,
                    timeout=int(self.timeout * 1000),
                    wait_until="domcontentloaded",
                )
                await page.wait_for_timeout(2500)
                content = await page.content()
                await browser.close()
                return content, content.encode("utf-8")
        except Exception as e:
            logger.warning(
                f"Playwright dynamic fetch failed for {url} ({e}), falling back to static fetch"
            )
            raw_bytes, _ = await self._get_raw_bytes(url)
            return raw_bytes.decode("utf-8", errors="replace"), raw_bytes

    def _clean_and_extract(
        self, html_content: str, base_url: str
    ) -> tuple[str, list[ExtractedTable], list[str], str]:
        """Clean boilerplate from HTML and extract text, tables, and discovered PDF/notice links."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract page title
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else ""

        # Extract discovered links (especially PDF notice links per ADR-012)
        discovered_links: list[str] = []
        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag.get("href")
            href = str(raw_href).strip() if raw_href else ""
            if href:
                full_url = urljoin(base_url, href)
                if (
                    href.lower().endswith(".pdf")
                    or "download" in href.lower()
                    or "circular" in href.lower()
                ):
                    discovered_links.append(full_url)

        # Extract tables before removing tags
        tables: list[ExtractedTable] = []
        for t_idx, table_tag in enumerate(soup.find_all("table")):
            headers: list[str] = []
            rows: list[list[str]] = []

            # Headers
            header_row = table_tag.find("tr")
            if header_row:
                th_cells = header_row.find_all(["th", "td"])
                headers = [th.get_text().strip() for th in th_cells]

            # Rows
            all_rows = table_tag.find_all("tr")
            start_idx = 1 if headers and len(all_rows) > 1 else 0
            for row_tag in all_rows[start_idx:]:
                cells = [td.get_text().strip() for td in row_tag.find_all(["td", "th"])]
                if any(cells):
                    rows.append(cells)

            if headers or rows:
                tables.append(
                    ExtractedTable(
                        headers=headers,
                        rows=rows,
                        title=f"Table {t_idx + 1}",
                    )
                )

        # Strip boilerplate elements
        for tag in soup(
            ["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"]
        ):
            tag.decompose()

        # Extract clean structured text
        text_blocks: list[str] = []
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote"]):
            text = element.get_text().strip()
            if text:
                if element.name.startswith("h"):
                    level = element.name[1]
                    text_blocks.append(f"{'#' * int(level)} {text}")
                elif element.name == "li":
                    text_blocks.append(f"• {text}")
                else:
                    text_blocks.append(text)

        cleaned_text = "\n\n".join(text_blocks)
        if not cleaned_text:
            # Fallback to get_text() if semantic tags are missing
            cleaned_text = soup.get_text(separator="\n").strip()
            cleaned_text = re.sub(r"\n\s*\n", "\n\n", cleaned_text)

        return cleaned_text, tables, discovered_links, title

    async def fetch(self, source: str, **kwargs: Any) -> FetchedDocument:
        """Fetch and parse HTML content from URL or local file."""
        use_pw = kwargs.get("use_playwright", self.use_playwright)

        if os.path.exists(source) and os.path.isfile(source):
            with open(source, "rb") as f:
                raw_bytes = f.read()
            html_text = raw_bytes.decode("utf-8", errors="replace")
            base_meta = {"file_size": len(raw_bytes), "local_file": True, "file_path": source}
        elif use_pw or "ecajmer.ac.in" in source.lower():
            html_text, raw_bytes = await self._fetch_dynamic_html(source)
            base_meta = {"file_size": len(raw_bytes), "local_file": False, "dynamic_rendered": True}
        else:
            raw_bytes, base_meta = await self._get_raw_bytes(source)
            html_text = raw_bytes.decode("utf-8", errors="replace")

        cleaned_text, tables, discovered_links, page_title = self._clean_and_extract(
            html_text, source
        )

        # If tables exist, append markdown tables to text representation
        if tables:
            table_md_blocks = [
                f"\n\n### Extracted Table ({t.title})\n" + t.to_markdown() for t in tables
            ]
            cleaned_text += "\n" + "\n".join(table_md_blocks)

        metadata: dict[str, Any] = {
            **base_meta,
            "title": page_title or kwargs.get("title", ""),
            "discovered_pdf_links": discovered_links,
            "table_count": len(tables),
        }

        return FetchedDocument(
            source_url=source,
            source_type=self.source_type,
            raw_content=raw_bytes,
            extracted_text=cleaned_text,
            tables=tables,
            metadata=metadata,
        )


async def fetch_html(
    source: str, timeout: float = 30.0, use_playwright: bool = False, **kwargs: Any
) -> FetchedDocument:
    """Convenience helper to fetch an HTML document."""
    fetcher = HTMLFetcher(timeout=timeout, use_playwright=use_playwright)
    return await fetcher.fetch(source, **kwargs)
