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


def extract_semester(text: str) -> str | None:
    """Extract academic semester from text (e.g. 1st to 8th sem, Roman I-VIII)."""
    if not text:
        return None

    roman_map = {
        "i": "1st Sem",
        "ii": "2nd Sem",
        "iii": "3rd Sem",
        "iv": "4th Sem",
        "v": "5th Sem",
        "vi": "6th Sem",
        "vii": "7th Sem",
        "viii": "8th Sem",
    }

    # Match standard forms: "3rd Sem", "3rd Semester", "Sem 3"
    m = re.search(r"\b([1-8])(?:st|nd|rd|th)?\s*(?:sem(?:ester)?)\b", text, re.IGNORECASE)
    if m:
        num = m.group(1)
        suffix = "st" if num == "1" else "nd" if num == "2" else "rd" if num == "3" else "th"
        return f"{num}{suffix} Sem"

    m_sem = re.search(r"\bsem(?:ester)?[\s:-]*([1-8])\b", text, re.IGNORECASE)
    if m_sem:
        num = m_sem.group(1)
        suffix = "st" if num == "1" else "nd" if num == "2" else "rd" if num == "3" else "th"
        return f"{num}{suffix} Sem"

    m_roman = re.search(
        r"\b(i{1,3}|iv|v|vi{1,3}|vii|viii)(?:st|nd|rd|th)?\s*(?:sem(?:ester)?)\b",
        text,
        re.IGNORECASE,
    )
    if m_roman:
        return roman_map.get(m_roman.group(1).lower())

    return None


def extract_notice_sno(text: str) -> str | None:
    """Extract official notice serial number or circular reference code."""
    if not text:
        return None

    patterns = [
        r"(?:Notice\s*(?:S\.?\s*No|No|Ref|Ref\.?\s*No)[\.:\s]*)([A-Za-z0-9/\-_()\.]{3,40})",
        r"(?:Order\s*No[\.:\s]*)([A-Za-z0-9/\-_()\.]{3,40})",
        r"\b(ECA/[A-Za-z0-9/\-_()\.]{3,35})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def extract_academic_year(text: str) -> str | None:
    """Extract academic session or year (e.g. 2025-26, 2026-27)."""
    if not text:
        return None

    m = re.search(r"\b(20\d{2}\s*[-/]\s*(?:20)?\d{2})\b", text)
    if m:
        return m.group(1).replace(" ", "")
    return None


class SemanticChunker:
    """Chunks documents along semantic boundaries (headings, paragraphs, tables) with overlap."""

    def __init__(
        self,
        target_tokens: int = 800,
        min_tokens: int = 150,
        max_tokens: int = 1200,
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

        if not title and raw_text:
            first_heading = re.search(r"^#\s+([^\n]+)", raw_text, re.MULTILINE)
            if first_heading:
                title = first_heading.group(1).strip()

        # Inferred metadata attributes
        doc_type = fetched.metadata.get("doc_type") or infer_doc_type(
            title=title, url=fetched.source_url, text=raw_text
        )
        doc_date = fetched.metadata.get("document_date") or extract_document_date(raw_text)
        doc_semester = (
            fetched.metadata.get("semester")
            or extract_semester(raw_text)
            or extract_semester(title)
        )
        doc_sno = fetched.metadata.get("sno") or extract_notice_sno(raw_text)
        doc_year = fetched.metadata.get("academic_year") or extract_academic_year(raw_text)

        base_meta = {
            "source_url": fetched.source_url,
            "source_type": fetched.source_type,
            "department": dept,
            "owner": doc_owner,
            "title": title,
            "doc_type": doc_type,
            "document_date": doc_date,
            "semester": doc_semester,
            "notice_sno": doc_sno,
            "academic_year": doc_year,
        }

        # 1. Gather all tables (both pre-extracted and markdown tables from OCR text)
        existing_tables: list[ExtractedTable] = list(fetched.tables)
        if raw_text:
            # Parse any native markdown tables embedded in text that were not yet in fetched.tables
            md_tables = parse_markdown_tables(raw_text)
            for mdt in md_tables:
                if not any(
                    t.headers == mdt.headers and t.rows == mdt.rows for t in existing_tables
                ):
                    existing_tables.append(mdt)

        # 2. Process structured tables as intact individual chunks with context breadcrumbs
        for t_idx, table in enumerate(existing_tables):
            table_md = table.to_markdown()
            row_statements = table.to_row_statements()

            table_context = title or (dept + " Notice" if dept else "Institutional Notice")
            if table.title:
                table_context = f"{table_context} > {table.title}"

            content_parts = [
                f"[Context: {table_context}]\n\n### Table {t_idx + 1}: {table.title or 'Tabular Data'}\n\n{table_md}"
            ]
            if row_statements:
                content_parts.append(
                    "**Row Statements:**\n" + "\n".join(f"- {s}" for s in row_statements)
                )

            table_content = "\n\n".join(content_parts)
            table_token_count = count_tokens(table_content)
            table_sem = extract_semester(table_content) or doc_semester

            chunk_meta = {
                **base_meta,
                "is_table": True,
                "table_index": t_idx,
                "page_number": table.page_number,
                "breadcrumb": table_context,
                "semester": table_sem,
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

        # Split text into sections along Markdown headings (#, ##, ###) while tracking breadcrumb hierarchy
        sections_with_breadcrumbs = self._split_markdown_sections_with_breadcrumbs(clean_text)
        if not sections_with_breadcrumbs:
            return chunks

        current_paragraphs: list[str] = []
        current_token_count = 0
        current_page_num: int | None = None
        chunk_breadcrumb: str = ""

        for section, breadcrumb in sections_with_breadcrumbs:
            page_match = re.search(r"--- Page (\d+)", section)
            if page_match:
                current_page_num = int(page_match.group(1))

            effective_breadcrumb = breadcrumb or chunk_breadcrumb or title
            sec_tokens = count_tokens(section)

            # Topic boundary check: If breadcrumb changes to a different heading hierarchy,
            # flush previous section to keep topical boundaries intact
            breadcrumb_changed = bool(
                chunk_breadcrumb and breadcrumb and chunk_breadcrumb != breadcrumb
            )
            exceeds_target = (
                current_token_count + sec_tokens > self.target_tokens
                and current_token_count >= self.min_tokens
            )

            if (breadcrumb_changed or exceeds_target) and current_paragraphs:
                raw_chunk = "\n\n".join(current_paragraphs)
                chunk_content = (
                    f"[Context: {chunk_breadcrumb}]\n\n{raw_chunk}"
                    if chunk_breadcrumb
                    else raw_chunk
                )
                chunks.append(
                    ChunkData(
                        content=chunk_content,
                        token_count=count_tokens(chunk_content),
                        chunk_index=chunk_idx,
                        metadata={
                            **base_meta,
                            "is_table": False,
                            "page_number": current_page_num,
                            "breadcrumb": chunk_breadcrumb,
                            "semester": extract_semester(raw_chunk) or doc_semester,
                        },
                    )
                )
                chunk_idx += 1
                current_paragraphs = []
                current_token_count = 0
                chunk_breadcrumb = ""

            # If a single section is larger than max_tokens, split it by paragraph/sentence
            if sec_tokens > self.max_tokens:
                sub_chunks = self._chunk_large_section(
                    section,
                    base_meta,
                    chunk_idx,
                    page_number=current_page_num,
                    breadcrumb=effective_breadcrumb,
                )
                chunks.extend(sub_chunks)
                chunk_idx += len(sub_chunks)
                continue

            if not chunk_breadcrumb:
                chunk_breadcrumb = effective_breadcrumb

            current_paragraphs.append(section)
            current_token_count += sec_tokens

        # Flush final remaining paragraphs
        if current_paragraphs:
            raw_chunk = "\n\n".join(current_paragraphs)
            final_breadcrumb = chunk_breadcrumb or title
            chunk_content = (
                f"[Context: {final_breadcrumb}]\n\n{raw_chunk}" if final_breadcrumb else raw_chunk
            )
            chunks.append(
                ChunkData(
                    content=chunk_content,
                    token_count=count_tokens(chunk_content),
                    chunk_index=chunk_idx,
                    metadata={
                        **base_meta,
                        "is_table": False,
                        "page_number": current_page_num,
                        "breadcrumb": final_breadcrumb,
                        "semester": extract_semester(raw_chunk) or doc_semester,
                    },
                )
            )

        return chunks

    def _split_markdown_sections_with_breadcrumbs(self, text: str) -> list[tuple[str, str]]:
        """Split text along Markdown headings (#, ##, ###) while maintaining the heading hierarchy stack."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split on Markdown headers while keeping the header text
        blocks = re.split(r"(?=(?:\n|^)#{1,4}\s+|\n---\s+Page|\n---\n)", text)
        results: list[tuple[str, str]] = []
        heading_stack: dict[int, str] = {}

        for block in blocks:
            clean = block.strip()
            if not clean:
                continue

            # Detect if this block introduces a Markdown heading
            header_match = re.match(r"^(#{1,4})\s+(.+?)(?:\n|$)", clean)
            if header_match:
                level = len(header_match.group(1))
                h_title = header_match.group(2).strip()
                # Clear all deeper levels
                heading_stack = {k: v for k, v in heading_stack.items() if k < level}
                heading_stack[level] = h_title

            current_breadcrumb = " > ".join(heading_stack[k] for k in sorted(heading_stack.keys()))

            # Sub-split blocks by double newlines if they are multi-paragraph
            sub_paragraphs = clean.split("\n\n")
            for sub_p in sub_paragraphs:
                p_clean = sub_p.strip()
                if p_clean:
                    results.append((p_clean, current_breadcrumb))

        return results

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
        breadcrumb: str = "",
    ) -> list[ChunkData]:
        """Sub-split an oversized section by sentences with overlap and context breadcrumb."""
        sentences = re.split(r"(?<=[.?!])\s+", section)
        chunks: list[ChunkData] = []
        current: list[str] = []
        tokens = 0
        idx = start_index

        for sent in sentences:
            st = count_tokens(sent)
            if tokens + st > self.target_tokens and tokens >= self.min_tokens:
                raw_chunk = " ".join(current)
                chunk_text = f"[Context: {breadcrumb}]\n\n{raw_chunk}" if breadcrumb else raw_chunk
                chunks.append(
                    ChunkData(
                        content=chunk_text,
                        token_count=count_tokens(chunk_text),
                        chunk_index=idx,
                        metadata={
                            **base_meta,
                            "is_table": False,
                            "page_number": page_number,
                            "breadcrumb": breadcrumb,
                            "semester": extract_semester(raw_chunk) or base_meta.get("semester"),
                        },
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
            raw_chunk = " ".join(current)
            chunk_text = f"[Context: {breadcrumb}]\n\n{raw_chunk}" if breadcrumb else raw_chunk
            chunks.append(
                ChunkData(
                    content=chunk_text,
                    token_count=count_tokens(chunk_text),
                    chunk_index=idx,
                    metadata={
                        **base_meta,
                        "is_table": False,
                        "page_number": page_number,
                        "breadcrumb": breadcrumb,
                        "semester": extract_semester(raw_chunk) or base_meta.get("semester"),
                    },
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
