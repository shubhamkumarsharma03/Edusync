from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RetrievedChunk:
    """Represents a retrieved document chunk with similarity scores and institutional metadata."""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float
    source_url: str
    last_verified: datetime
    token_count: int
    department: str | None = None
    owner: str | None = None
    vector_score: float | None = None
    keyword_score: float | None = None
    rank: int | None = None
