import re
from typing import Any

from ingestion.schemas import ChunkData, ExtractedTable, FetchedDocument
from ingestion.table_extractor import parse_markdown_tables


def count_tokens(text: str) -> int:
    """Estimate token count for a text string.

    Standard word-to-token ratio (~1.33 tokens per whitespace word / ~4 chars per token).
    """
    if not text or not text.strip():
        return 0
    words = text.split()
    return max(1, int(len(words) * 1.33))


def infer_doc_type(title: str, url: str, text: str) -> str:
    """Infer institutional document category from title, URL path, and leading text."""
    combined = f"{title} {url} {text[:1000]}".lower()
    if any(
        k in combined
        for k in ["time table", "timetable", "time-table", "schedule", "datesheet", "date sheet"]
    ):
        return "timetable"
    if any(k in combined for k in ["circular", "office order", "notification", "office-order"]):
        return "circular"
    if any(k in combined for k in ["syllabus", "curriculum", "course structure", "scheme"]):
        return "syllabus"
    if any(k in combined for k in ["fee", "dues", "tuition", "hostel fee", "scholarship"]):
        return "fee_notice"
    if any(k in combined for k in ["exam", "examination", "mid-term", "end-term", "admit card"]):
        return "exam_notice"
    return "notice"


def extract_document_date(text: str) -> str | None:
    """Extract first documented date from header or content using standard regex patterns."""
    if not text:
        return None

    # Check top portion of document first
    header_snippet = text[:1500]
    date_patterns = [
        # DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
        r"\b(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})\b",
        # DD Month YYYY (e.g., 12 Sept 2026, 12 September 2026)
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
        # Month DD, YYYY (e.g., September 12, 2026)
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b",
    ]
    for pat in date_patterns:
        match = re.search(pat, header_snippet, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


class SemanticChunker:
    """Chunks documents along semantic boundaries (headings, paragraphs, tables) with overlap."""

    def __init__(
        self,
        target_tokens: int = 400,
        min_tokens: int = 150,
        max_tokens: int = 500,
        overlap_ratio: float = 0.15,
    ) -> None:
        self.target_tokens = target_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_ratio = overlap_ratio

    def chunk_document(
        self,
        fetched: FetchedDocument,
        department: str | None = None,
        owner: str | None = None,
    ) -> list[ChunkData]:
        """Split a FetchedDocument into a list of contextual ChunkData instances."""
        chunks: list[ChunkData] = []
        chunk_idx = 0

        dept = department or fetched.metadata.get("department")
        doc_owner = owner or fetched.metadata.get("owner")
        title = fetched.metadata.get("title", "")
        raw_text = fetched.extracted_text.strip()

        # Inferred metadata attributes
        doc_type = fetched.metadata.get("doc_type") or infer_doc_type(
            title=title, url=fetched.source_url, text=raw_text
        )
        doc_date = fetched.metadata.get("document_date") or extract_document_date(raw_text)

        base_meta = {
            "source_url": fetched.source_url,
            "source_type": fetched.source_type,
            "department": dept,
            "owner": doc_owner,
            "title": title,
            "doc_type": doc_type,
            "document_date": doc_date,
        }

        # 1. Gather all tables (both pre-extracted and markdown tables from OCR text)
        existing_tables: list[ExtractedTable] = list(fetched.tables)
        if raw_text:
            # Parse any native markdown tables embedded in text that were not yet in fetched.tables
            md_tables = parse_markdown_tables(raw_text)
            for mdt in md_tables:
                # Check for duplication
                if not any(
                    t.headers == mdt.headers and t.rows == mdt.rows for t in existing_tables
                ):
                    existing_tables.append(mdt)

        # 2. Process structured tables as intact individual chunks (ADR-004 & TDD §5.2)
        for t_idx, table in enumerate(existing_tables):
            table_md = table.to_markdown()
            row_statements = table.to_row_statements()

            content_parts = [
                f"### Table {t_idx + 1}: {table.title or 'Tabular Data'}\n\n{table_md}"
            ]
            if row_statements:
                content_parts.append(
                    "**Row Statements:**\n" + "\n".join(f"- {s}" for s in row_statements)
                )

            table_content = "\n\n".join(content_parts)
            table_token_count = count_tokens(table_content)

            chunk_meta = {
                **base_meta,
                "is_table": True,
                "table_index": t_idx,
                "page_number": table.page_number,
            }

            chunks.append(
                ChunkData(
                    content=table_content,
                    token_count=table_token_count,
                    chunk_index=chunk_idx,
                    metadata=chunk_meta,
                )
            )
            chunk_idx += 1

        # 3. Process text content along semantic boundaries (headings & sections)
        if not raw_text:
            return chunks

        # Remove table markdown blocks already handled as separate chunks
        clean_text = re.sub(
            r"### Extracted Table \(.*?\)\n.*?(?=\n\n#|\n\n---|--- Page|\Z)",
            "",
            raw_text,
            flags=re.DOTALL,
        )
        clean_text = clean_text.strip()

        if not clean_text:
            return chunks

        # Split text into sections along Markdown headings (#, ##, ###) or page dividers (---)
        sections = self._split_markdown_sections(clean_text)
        if not sections:
            return chunks

        current_paragraphs: list[str] = []
        current_token_count = 0
        current_page_num: int | None = None

        for section in sections:
            # Check for page number indicator
            page_match = re.search(r"--- Page (\d+)", section)
            if page_match:
                current_page_num = int(page_match.group(1))

            sec_tokens = count_tokens(section)

            # If a single section is larger than max_tokens, split it by paragraph/sentence
            if sec_tokens > self.max_tokens:
                if current_paragraphs:
                    chunk_content = "\n\n".join(current_paragraphs)
                    chunks.append(
                        ChunkData(
                            content=chunk_content,
                            token_count=current_token_count,
                            chunk_index=chunk_idx,
                            metadata={
                                **base_meta,
                                "is_table": False,
                                "page_number": current_page_num,
                            },
                        )
                    )
                    chunk_idx += 1
                    current_paragraphs = []
                    current_token_count = 0

                sub_chunks = self._chunk_large_section(
                    section, base_meta, chunk_idx, page_number=current_page_num
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)
                continue

            # If adding section exceeds target_tokens, flush and overlap
            if (
                current_token_count + sec_tokens > self.target_tokens
                and current_token_count >= self.min_tokens
            ):
                chunk_content = "\n\n".join(current_paragraphs)
                chunks.append(
                    ChunkData(
                        content=chunk_content,
                        token_count=current_token_count,
                        chunk_index=chunk_idx,
                        metadata={**base_meta, "is_table": False, "page_number": current_page_num},
                    )
                )
                chunk_idx += 1

                overlap_prefix = self._get_overlap_prefix(current_paragraphs)
                current_paragraphs = [overlap_prefix, section] if overlap_prefix else [section]
                current_token_count = sum(count_tokens(p) for p in current_paragraphs)
            else:
                current_paragraphs.append(section)
                current_token_count += sec_tokens

        # Flush final remaining paragraphs
        if current_paragraphs:
            chunk_content = "\n\n".join(current_paragraphs)
            chunks.append(
                ChunkData(
                    content=chunk_content,
                    token_count=current_token_count,
                    chunk_index=chunk_idx,
                    metadata={**base_meta, "is_table": False, "page_number": current_page_num},
                )
            )

        return chunks

    def _split_markdown_sections(self, text: str) -> list[str]:
        """Split text along Markdown headings (#, ##, ###), page dividers (---), or double newlines."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split on Markdown headers (## ) or page headers while keeping the header text
        blocks = re.split(r"(?=(?:\n|^)#{1,4}\s+|\n---\s+Page|\n---\n)", text)
        sections: list[str] = []

        for block in blocks:
            clean = block.strip()
            if not clean:
                continue

            # Sub-split blocks by double newlines if they are multi-paragraph
            sub_paragraphs = clean.split("\n\n")
            for sub_p in sub_paragraphs:
                p_clean = sub_p.strip()
                if p_clean:
                    sections.append(p_clean)

        return sections

    def _get_overlap_prefix(self, paragraphs: list[str]) -> str:
        """Extract trailing sentences from the last paragraph for sliding window overlap."""
        if not paragraphs:
            return ""

        last_para = paragraphs[-1]
        sentences = re.split(r"(?<=[.?!])\s+", last_para)
        overlap_tokens_target = int(self.target_tokens * self.overlap_ratio)

        selected: list[str] = []
        token_sum = 0

        for sentence in reversed(sentences):
            st = count_tokens(sentence)
            if token_sum + st <= overlap_tokens_target or not selected:
                selected.insert(0, sentence)
                token_sum += st
            else:
                break

        return " ".join(selected)

    def _chunk_large_section(
        self,
        section: str,
        base_meta: dict[str, Any],
        start_index: int,
        page_number: int | None = None,
    ) -> list[ChunkData]:
        """Sub-split an oversized section by sentences with overlap."""
        sentences = re.split(r"(?<=[.?!])\s+", section)
        chunks: list[ChunkData] = []
        current: list[str] = []
        tokens = 0
        idx = start_index

        for sent in sentences:
            st = count_tokens(sent)
            if tokens + st > self.target_tokens and tokens >= self.min_tokens:
                chunk_text = " ".join(current)
                chunks.append(
                    ChunkData(
                        content=chunk_text,
                        token_count=tokens,
                        chunk_index=idx,
                        metadata={**base_meta, "is_table": False, "page_number": page_number},
                    )
                )
                idx += 1
                # 1-sentence overlap
                current = [current[-1], sent] if current else [sent]
                tokens = sum(count_tokens(s) for s in current)
            else:
                current.append(sent)
                tokens += st

        if current:
            chunks.append(
                ChunkData(
                    content=" ".join(current),
                    token_count=tokens,
                    chunk_index=idx,
                    metadata={**base_meta, "is_table": False, "page_number": page_number},
                )
            )

        return chunks


def chunk_document(
    fetched: FetchedDocument,
    department: str | None = None,
    owner: str | None = None,
    **kwargs: Any,
) -> list[ChunkData]:
    """Convenience helper to chunk a FetchedDocument."""
    chunker = SemanticChunker(**kwargs)
    return chunker.chunk_document(fetched, department=department, owner=owner)
