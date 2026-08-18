from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal["pdf", "html", "sheet"]


class ExtractedTable(BaseModel):
    """Structured representation of an extracted table."""

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    page_number: int | None = None
    title: str | None = None

    def to_markdown(self) -> str:
        """Render table in standard GitHub Markdown format."""
        if not self.headers and not self.rows:
            return ""

        headers = (
            self.headers
            if self.headers
            else [f"Col {i+1}" for i in range(len(self.rows[0]))] if self.rows else []
        )
        col_count = len(headers)

        lines: list[str] = []
        if self.title:
            lines.append(f"**Table: {self.title}**\n")

        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * col_count) + " |")

        for row in self.rows:
            # Pad or truncate row to match header count
            padded_row = list(row) + [""] * (col_count - len(row))
            clean_cells = [cell.replace("\n", " ").strip() for cell in padded_row[:col_count]]
            lines.append("| " + " | ".join(clean_cells) + " |")

        return "\n".join(lines)

    def to_row_statements(self) -> list[str]:
        """Convert each table row into a self-contained contextual statement.

        This preserves relational semantics (e.g. Day x Period x Faculty x Room)
        for chunking and embeddings without losing header context.
        """
        if not self.rows:
            return []

        headers = (
            self.headers if self.headers else [f"Field {i+1}" for i in range(len(self.rows[0]))]
        )
        statements: list[str] = []

        for row in self.rows:
            parts: list[str] = []
            for i, val in enumerate(row):
                header = headers[i] if i < len(headers) else f"Field {i+1}"
                val_clean = str(val).strip()
                if val_clean:
                    parts.append(f"{header}: {val_clean}")
            if parts:
                statements.append(", ".join(parts))

        return statements


class FetchedDocument(BaseModel):
    """Output contract for fetched and parsed institutional documents."""

    source_url: str
    source_type: SourceType
    raw_content: bytes
    extracted_text: str
    tables: list[ExtractedTable] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkData(BaseModel):
    """Output representation of a semantic document chunk ready for vector embedding."""

    content: str
    token_count: int
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)
