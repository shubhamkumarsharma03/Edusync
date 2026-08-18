import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ingestion.schemas import FetchedDocument


def normalize_content(content: str | bytes, source_type: str = "pdf") -> bytes:
    """Normalize content before hashing to eliminate false-positive changes.

    For text/HTML/Sheet strings:
    - Normalizes line endings (\r\n -> \n)
    - Strips leading/trailing whitespace per line
    - Omits empty lines

    For binary data (e.g. PDFs):
    - Returns raw bytes if string cannot be decoded
    """
    if isinstance(content, bytes):
        if source_type in ("html", "sheet"):
            try:
                text = content.decode("utf-8")
                return _normalize_text(text).encode("utf-8")
            except UnicodeDecodeError:
                return content
        return content

    return _normalize_text(content).encode("utf-8")


def _normalize_text(text: str) -> str:
    """Internal helper to sanitize text content."""
    # Standardize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip whitespace per line and omit empty lines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


def compute_hash(content: str | bytes, source_type: str = "pdf") -> str:
    """Compute a deterministic SHA-256 hex digest for document content."""
    normalized_bytes = normalize_content(content, source_type=source_type)
    return hashlib.sha256(normalized_bytes).hexdigest()


def compute_document_hash(fetched: "FetchedDocument") -> str:
    """Compute deterministic SHA-256 hash for a FetchedDocument.

    - For HTML & Sheets: Hashes normalized extracted_text + tables (ignores raw ephemeral scripts).
    - For PDFs: Hashes raw binary payload.
    """
    if fetched.source_type in ("html", "sheet"):
        return compute_hash(fetched.extracted_text, source_type=fetched.source_type)
    return compute_hash(fetched.raw_content, source_type=fetched.source_type)
