import re
from typing import Any

from ingestion.schemas import ChunkData, FetchedDocument


def count_tokens(text: str) -> int:
    """Estimate token count for a text string.

    Standard word-to-token ratio (~1.33 tokens per whitespace word / ~4 chars per token).
    """
    if not text or not text.strip():
        return 0
    words = text.split()
    return max(1, int(len(words) * 1.33))


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

        base_meta = {
            "source_url": fetched.source_url,
            "source_type": fetched.source_type,
            "department": dept,
            "owner": doc_owner,
            "title": title,
        }

        # 1. Process structured tables as intact individual chunks (ADR-004 & TDD §5.2)
        for t_idx, table in enumerate(fetched.tables):
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

        # 2. Process text content along semantic boundaries (headings & paragraphs)
        raw_text = fetched.extracted_text.strip()
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

        # Segment by headings (#), page dividers (---), or double newlines
        paragraphs = self._split_paragraphs(clean_text)
        if not paragraphs:
            return chunks

        current_paragraphs: list[str] = []
        current_token_count = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)

            # If a single paragraph is larger than max_tokens, split it by sentence
            if para_tokens > self.max_tokens:
                if current_paragraphs:
                    # Flush existing accumulation
                    chunk_content = "\n\n".join(current_paragraphs)
                    chunks.append(
                        ChunkData(
                            content=chunk_content,
                            token_count=current_token_count,
                            chunk_index=chunk_idx,
                            metadata={**base_meta, "is_table": False},
                        )
                    )
                    chunk_idx += 1
                    current_paragraphs = []
                    current_token_count = 0

                # Split large paragraph by sentences
                sentence_chunks = self._chunk_large_paragraph(para, base_meta, chunk_idx)
                chunks.extend(sentence_chunks)
                chunk_idx += len(sentence_chunks)
                continue

            # If adding paragraph exceeds target_tokens, emit chunk and apply sliding window overlap
            if (
                current_token_count + para_tokens > self.target_tokens
                and current_token_count >= self.min_tokens
            ):
                chunk_content = "\n\n".join(current_paragraphs)
                chunks.append(
                    ChunkData(
                        content=chunk_content,
                        token_count=current_token_count,
                        chunk_index=chunk_idx,
                        metadata={**base_meta, "is_table": False},
                    )
                )
                chunk_idx += 1

                # Calculate overlap: retain trailing paragraph or sentences
                overlap_prefix = self._get_overlap_prefix(current_paragraphs)
                current_paragraphs = [overlap_prefix, para] if overlap_prefix else [para]
                current_token_count = sum(count_tokens(p) for p in current_paragraphs)
            else:
                current_paragraphs.append(para)
                current_token_count += para_tokens

        # Flush final remaining paragraphs
        if current_paragraphs:
            chunk_content = "\n\n".join(current_paragraphs)
            chunks.append(
                ChunkData(
                    content=chunk_content,
                    token_count=current_token_count,
                    chunk_index=chunk_idx,
                    metadata={**base_meta, "is_table": False},
                )
            )

        return chunks

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text on headings (#), page breaks (---), and paragraph boundaries."""
        # Standardize line breaks
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        raw_blocks = text.split("\n\n")
        paragraphs: list[str] = []

        for block in raw_blocks:
            clean = block.strip()
            if clean:
                paragraphs.append(clean)

        return paragraphs

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

    def _chunk_large_paragraph(
        self,
        paragraph: str,
        base_meta: dict[str, Any],
        start_index: int,
    ) -> list[ChunkData]:
        """Sub-split an oversized paragraph by sentences with overlap."""
        sentences = re.split(r"(?<=[.?!])\s+", paragraph)
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
                        metadata={**base_meta, "is_table": False},
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
                    metadata={**base_meta, "is_table": False},
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
