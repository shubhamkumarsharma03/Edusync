from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
    rerank_score: float | None = None
    rank: int | None = None


class SourceCitation(BaseModel):
    """Institutional source metadata attached to a generated response (TDD §6 / PRD FR-16)."""

    document: str = Field(..., description="Document title, department or source filename")
    last_verified: datetime | str = Field(
        ..., description="Timestamp when source was last verified"
    )
    url: str = Field(..., description="Direct URL to official circular or document")


class GenerationResult(BaseModel):
    """Grounded answer generated from verified chunks with source citations."""

    answer: str = Field(..., description="Grounded response text")
    sources: list[SourceCitation] = Field(
        default_factory=list, description="List of source citations"
    )
    confidence: float = Field(..., description="Confidence score of top retrieved context")
    is_fallback: bool = Field(default=False, description="True if response is a fallback message")
