from datetime import UTC, datetime
from uuid import uuid4

from retrieval.confidence_gate import (
    ConfidenceGate,
    ConfidenceLevel,
)
from retrieval.schemas import RetrievedChunk


def create_dummy_chunk(
    score: float, rerank_score: float | None = None, department: str | None = "Examination"
) -> RetrievedChunk:
    """Helper to create dummy RetrievedChunk for testing."""
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="Sample content for testing confidence gating.",
        score=score,
        rerank_score=rerank_score if rerank_score is not None else score,
        source_url="https://ecajmer.ac.in/notices/exam_schedule.pdf",
        last_verified=datetime.now(UTC),
        token_count=10,
        department=department,
    )


def test_confidence_gate_initialization():
    """Test ConfidenceGate initializes with default and custom thresholds."""
    gate = ConfidenceGate()
    assert gate.threshold == 0.55

    custom_gate = ConfidenceGate(threshold=0.65)
    assert custom_gate.threshold == 0.65


def test_confidence_classification():
    """Test classifying scores into High, Medium, and Low."""
    gate = ConfidenceGate(threshold=0.55)

    assert gate.classify_confidence_level(0.85) == ConfidenceLevel.HIGH
    assert gate.classify_confidence_level(0.75) == ConfidenceLevel.HIGH
    assert gate.classify_confidence_level(0.70) == ConfidenceLevel.MEDIUM
    assert gate.classify_confidence_level(0.55) == ConfidenceLevel.MEDIUM
    assert gate.classify_confidence_level(0.54) == ConfidenceLevel.LOW
    assert gate.classify_confidence_level(0.10) == ConfidenceLevel.LOW


def test_confidence_gate_pass_high():
    """Test that a high scoring chunk passes with HIGH confidence level."""
    gate = ConfidenceGate(threshold=0.55)
    chunk = create_dummy_chunk(score=0.88, rerank_score=0.88)

    result = gate.evaluate([chunk])

    assert result.passed is True
    assert result.is_fallback is False
    assert result.top_score == 0.88
    assert result.confidence_level == ConfidenceLevel.HIGH
    assert result.fallback_message is None
    assert len(result.qualifying_chunks) == 1
    assert result.qualifying_chunks[0].chunk_id == chunk.chunk_id


def test_confidence_gate_pass_medium():
    """Test that a medium scoring chunk (0.55 - 0.74) passes with MEDIUM confidence level."""
    gate = ConfidenceGate(threshold=0.55)
    chunk = create_dummy_chunk(score=0.62, rerank_score=0.62)

    result = gate.evaluate([chunk])

    assert result.passed is True
    assert result.is_fallback is False
    assert result.top_score == 0.62
    assert result.confidence_level == ConfidenceLevel.MEDIUM
    assert result.fallback_message is None
    assert len(result.qualifying_chunks) == 1


def test_confidence_gate_fail_below_threshold():
    """Test that chunks below threshold fail the gate and return fallback per PRD FR-15."""
    gate = ConfidenceGate(threshold=0.55)
    chunk = create_dummy_chunk(score=0.42, rerank_score=0.42, department="Accounts")

    result = gate.evaluate([chunk])

    assert result.passed is False
    assert result.is_fallback is True
    assert result.top_score == 0.42
    assert result.confidence_level == ConfidenceLevel.LOW
    assert result.fallback_message is not None
    assert "Accounts" in result.fallback_message
    assert len(result.qualifying_chunks) == 0


def test_confidence_gate_empty_chunks():
    """Test that evaluating an empty list safely returns fallback response."""
    gate = ConfidenceGate(threshold=0.55)

    result = gate.evaluate([])

    assert result.passed is False
    assert result.is_fallback is True
    assert result.top_score == 0.0
    assert result.confidence_level == ConfidenceLevel.LOW
    assert result.fallback_message == gate.DEFAULT_FALLBACK_MESSAGE
    assert len(result.qualifying_chunks) == 0


def test_confidence_gate_filters_lower_ranking_chunks():
    """Test that only qualifying chunks above threshold are returned."""
    gate = ConfidenceGate(threshold=0.55)
    chunk1 = create_dummy_chunk(score=0.78, rerank_score=0.78)
    chunk2 = create_dummy_chunk(score=0.58, rerank_score=0.58)
    chunk3 = create_dummy_chunk(score=0.30, rerank_score=0.30)

    result = gate.evaluate([chunk1, chunk2, chunk3])

    assert result.passed is True
    assert result.top_score == 0.78
    assert len(result.qualifying_chunks) == 2
    assert chunk1 in result.qualifying_chunks
    assert chunk2 in result.qualifying_chunks
    assert chunk3 not in result.qualifying_chunks


def test_confidence_gate_threshold_override():
    """Test that threshold can be dynamically overridden in evaluate()."""
    gate = ConfidenceGate(threshold=0.55)
    chunk = create_dummy_chunk(score=0.60, rerank_score=0.60)

    # Standard evaluate -> passes
    assert gate.evaluate([chunk]).passed is True

    # With higher threshold override -> fails
    result = gate.evaluate([chunk], threshold=0.70)
    assert result.passed is False
    assert result.is_fallback is True
