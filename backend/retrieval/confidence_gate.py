import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from api.config import get_settings
from retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class ConfidenceLevel(StrEnum):
    """Confidence levels for retrieved context to inform generation and frontend indicators."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ConfidenceGateResult:
    """Result returned by the ConfidenceGate after evaluating retrieved chunks."""

    passed: bool
    top_score: float
    confidence_level: ConfidenceLevel
    fallback_message: str | None
    qualifying_chunks: list[RetrievedChunk]

    @property
    def is_fallback(self) -> bool:
        """Helper to check if this query requires a fallback response."""
        return not self.passed


class ConfidenceGate:
    """Evaluates reranked search results against institutional confidence thresholds.

    Enforces the 'Trust Layer' requirement (PRD FR-15 / TDD §5.3):
    If top reranked score < CONFIDENCE_THRESHOLD (default: 0.55),
    fail the gate and trigger a safe fallback message without calling the LLM.
    """

    HIGH_CONFIDENCE_THRESHOLD: float = 0.75
    DEFAULT_FALLBACK_MESSAGE: str = (
        "I don't have verified information on this topic in the official college circulars or notices. "
        "Please check with the relevant department office or visit the official college website."
    )

    def __init__(self, threshold: float | None = None) -> None:
        settings = get_settings()
        raw_val = (
            threshold if threshold is not None else getattr(settings, "CONFIDENCE_THRESHOLD", 0.55)
        )
        self.threshold: float = float(raw_val)

    def classify_confidence_level(self, score: float) -> ConfidenceLevel:
        """Classify a normalized relevance score into High, Medium, or Low."""
        if score >= self.HIGH_CONFIDENCE_THRESHOLD:
            return ConfidenceLevel.HIGH
        elif score >= self.threshold:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def generate_fallback_message(self, department: str | None = None) -> str:
        """Generate a user-facing fallback message, optionally tailoring to a department."""
        if department:
            return (
                f"I don't have verified information on this in the official circulars. "
                f"Please check directly with the {department} Department or visit the college website."
            )
        return self.DEFAULT_FALLBACK_MESSAGE

    def evaluate(
        self,
        chunks: Sequence[RetrievedChunk],
        threshold: float | None = None,
    ) -> ConfidenceGateResult:
        """Evaluate a ranked sequence of retrieved chunks against the confidence threshold.

        Args:
            chunks: Sequence of candidate chunks, sorted by relevance score descending.
            threshold: Optional override for the confidence threshold.

        Returns:
            ConfidenceGateResult with pass/fail status, confidence level, and qualifying chunks.
        """
        active_threshold = self.threshold if threshold is None else threshold

        # If no candidate chunks were retrieved at all
        if not chunks:
            logger.info("Confidence gate: No chunks retrieved. Triggering fallback response.")
            return ConfidenceGateResult(
                passed=False,
                top_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                fallback_message=self.generate_fallback_message(),
                qualifying_chunks=[],
            )

        top_chunk = chunks[0]
        top_score = float(
            top_chunk.rerank_score if top_chunk.rerank_score is not None else top_chunk.score
        )
        confidence_level = self.classify_confidence_level(top_score)

        # Gate Check: Does the highest-scoring chunk meet the confidence threshold?
        if top_score < active_threshold:
            logger.warning(
                f"Confidence gate FAIL: Top score ({top_score:.4f}) is below threshold ({active_threshold:.4f}). "
                f"Triggering fallback message per PRD FR-15."
            )
            return ConfidenceGateResult(
                passed=False,
                top_score=top_score,
                confidence_level=ConfidenceLevel.LOW,
                fallback_message=self.generate_fallback_message(top_chunk.department),
                qualifying_chunks=[],
            )

        # Filter qualifying chunks: only return chunks that meet threshold
        qualifying = [
            chunk
            for chunk in chunks
            if (chunk.rerank_score if chunk.rerank_score is not None else chunk.score)
            >= active_threshold
        ]

        logger.info(
            f"Confidence gate PASS: Top score is {top_score:.4f} (level: {confidence_level.value}). "
            f"{len(qualifying)} qualifying chunks passed."
        )

        return ConfidenceGateResult(
            passed=True,
            top_score=top_score,
            confidence_level=confidence_level,
            fallback_message=None,
            qualifying_chunks=qualifying,
        )
