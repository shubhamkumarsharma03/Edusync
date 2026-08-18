import csv
import io
import logging
from typing import Any

from ingestion.fetchers.base import BaseFetcher
from ingestion.schemas import ExtractedTable, FetchedDocument, SourceType

logger = logging.getLogger(__name__)


class SheetFetcher(BaseFetcher):
    """Fetcher for Tabular and CSV/Sheet documents."""

    source_type: SourceType = "sheet"

    async def fetch(self, source: str, **kwargs: Any) -> FetchedDocument:
        """Fetch and parse CSV/TSV/Sheet documents into structured tables and normalized row statements."""
        raw_bytes, base_meta = await self._get_raw_bytes(source)

        try:
            # Decode CSV text (trying utf-8, latin-1 fallback)
            try:
                decoded_str = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                decoded_str = raw_bytes.decode("latin-1")

            # Sniff dialect for delimiter (comma, tab, semicolon)
            try:
                sample = decoded_str[:2048]
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = csv.excel  # default to standard comma delimiter

            reader = csv.reader(io.StringIO(decoded_str), dialect=dialect)
            all_rows = [row for row in reader if any(cell.strip() for cell in row)]

            if not all_rows:
                headers = []
                rows = []
            else:
                headers = [str(c).strip() for c in all_rows[0]]
                rows = [[str(c).strip() for c in row] for row in all_rows[1:]]

            table = ExtractedTable(
                headers=headers,
                rows=rows,
                title=kwargs.get("title") or "Sheet Data",
            )

            # Generate natural language row statements (ADR-004)
            row_statements = table.to_row_statements()

            # Format text body
            text_blocks: list[str] = [
                f"# Tabular Document: {table.title}",
                f"**Columns:** {', '.join(headers)}",
                f"**Total Records:** {len(rows)}",
                "\n### Structured Records (Row Statements):",
            ]
            for stmt in row_statements:
                text_blocks.append(f"• {stmt}")

            text_blocks.append("\n### Raw Table View:")
            text_blocks.append(table.to_markdown())

            extracted_text = "\n\n".join(text_blocks)

            metadata: dict[str, Any] = {
                **base_meta,
                "title": table.title,
                "row_count": len(rows),
                "column_count": len(headers),
                "columns": headers,
            }

            return FetchedDocument(
                source_url=source,
                source_type=self.source_type,
                raw_content=raw_bytes,
                extracted_text=extracted_text,
                tables=[table] if rows or headers else [],
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to parse sheet document from {source}: {e}")
            raise ValueError(f"Failed to parse CSV/Sheet from {source}: {e}") from e


async def fetch_sheet(source: str, timeout: float = 30.0, **kwargs: Any) -> FetchedDocument:
    """Convenience helper to fetch a CSV/Sheet document."""
    fetcher = SheetFetcher(timeout=timeout)
    return await fetcher.fetch(source, **kwargs)
