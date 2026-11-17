import logging
import re

from ingestion.schemas import ExtractedTable

logger = logging.getLogger(__name__)


def parse_markdown_tables(
    markdown_text: str,
    page_number: int | None = None,
    default_title_prefix: str = "Table",
) -> list[ExtractedTable]:
    """Extract and parse all Markdown tables from a markdown text string.

    Detects Markdown table syntax (| ... |) along with preceding title/heading context.
    Returns a list of validated ExtractedTable instances.
    """
    if not markdown_text or not markdown_text.strip():
        return []

    tables: list[ExtractedTable] = []
    lines = markdown_text.splitlines()

    i = 0
    table_count = 0

    while i < len(lines):
        line = lines[i].strip()

        # Check if line looks like a markdown table header row: starts and/or ends with '|' and contains '|'
        if "|" in line and (line.startswith("|") or line.endswith("|")):
            # Look ahead for separator row: | --- | --- | or |:---|---:|
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if is_markdown_separator_row(next_line):
                    # Found a table!
                    header_line = line
                    i += 2

                    data_rows: list[list[str]] = []
                    while i < len(lines):
                        row_line = lines[i].strip()
                        if not row_line or "|" not in row_line:
                            break
                        cells = split_markdown_cells(row_line)
                        data_rows.append(cells)
                        i += 1

                    raw_headers = split_markdown_cells(header_line)

                    # Look backwards for a preceding title or header
                    table_title = detect_preceding_title(
                        lines, header_line_idx=i - len(data_rows) - 2
                    )
                    if not table_title:
                        table_count += 1
                        page_str = f" (Page {page_number})" if page_number else ""
                        table_title = f"{default_title_prefix} {table_count}{page_str}"

                    # Normalize column counts
                    headers, normalized_rows = normalize_table_dimensions(raw_headers, data_rows)

                    extracted = ExtractedTable(
                        headers=headers,
                        rows=normalized_rows,
                        page_number=page_number,
                        title=table_title,
                    )

                    is_valid, reason = validate_table(extracted)
                    if is_valid:
                        tables.append(extracted)
                    else:
                        logger.debug(f"Skipping malformed markdown table: {reason}")
                    continue

        i += 1

    return tables


def split_markdown_cells(line: str) -> list[str]:
    """Split a Markdown table row into trimmed cell values."""
    trimmed = line.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|"):
        trimmed = trimmed[:-1]

    cells = [c.strip() for c in trimmed.split("|")]
    return cells


def is_markdown_separator_row(line: str) -> bool:
    """Check if a line matches Markdown table separator syntax: | --- | :---: | etc."""
    trimmed = line.strip()
    if not trimmed or "|" not in trimmed:
        return False

    cells = split_markdown_cells(trimmed)
    if not cells:
        return False

    # Each cell must consist of dashes and optional colons (for alignment)
    for cell in cells:
        clean = cell.replace(":", "").replace("-", "").strip()
        if clean != "" or len(cell.strip()) == 0:
            return False

    return True


def normalize_table_dimensions(
    headers: list[str],
    rows: list[list[str]],
) -> tuple[list[str], list[list[str]]]:
    """Ensure header length matches row cell count by padding or trimming."""
    max_cols = max(len(headers), max((len(r) for r in rows), default=0))
    if max_cols == 0:
        return [], []

    # Pad headers if shorter than max_cols
    normalized_headers = list(headers)
    while len(normalized_headers) < max_cols:
        normalized_headers.append(f"Col {len(normalized_headers) + 1}")

    # Pad or trim data rows
    normalized_rows: list[list[str]] = []
    for row in rows:
        padded = list(row) + [""] * (max_cols - len(row))
        normalized_rows.append(padded[:max_cols])

    return normalized_headers, normalized_rows


def detect_preceding_title(lines: list[str], header_line_idx: int) -> str | None:
    """Look backwards from a table's start line to find a title or heading."""
    check_idx = header_line_idx - 1
    # Check up to 3 non-empty lines backwards
    checked_count = 0
    while check_idx >= 0 and checked_count < 3:
        candidate = lines[check_idx].strip()
        check_idx -= 1
        if not candidate:
            continue

        checked_count += 1
        # Match markdown headers: # Title, ## Subtitle, ### Table: Timetable
        header_match = re.match(r"^#{1,6}\s+(.+)$", candidate)
        if header_match:
            return header_match.group(1).strip()

        # Match bold text: **Timetable ...** or Table: ...
        bold_match = re.match(r"^\*\*(?:Table:?\s*)?([^*]+)\*\*$", candidate, re.IGNORECASE)
        if bold_match:
            return bold_match.group(1).strip()

        if candidate.lower().startswith("table ") or candidate.lower().startswith("schedule "):
            return candidate

        # Stop looking backwards if standard prose text is encountered
        break

    return None


def validate_table(table: ExtractedTable) -> tuple[bool, str]:
    """Validate that an ExtractedTable has sufficient structure and content."""
    if not table.headers and not table.rows:
        return False, "Table is completely empty"

    col_count = len(table.headers) if table.headers else (len(table.rows[0]) if table.rows else 0)
    if col_count < 2:
        return False, f"Table has fewer than 2 columns ({col_count})"

    if not table.rows:
        return False, "Table has headers but no data rows"

    # Check if all cells in all rows are empty whitespace
    has_content = any(any(c.strip() for c in row) for row in table.rows)
    if not has_content:
        return False, "Table contains only empty cells"

    return True, "Valid"
