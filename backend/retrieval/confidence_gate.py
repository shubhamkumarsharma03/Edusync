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
    caveat: str | None = None

    @property
    def is_fallback(self) -> bool:
        """Helper to check if this query requires a fallback response."""
        return not self.passed


class ConfidenceGate:
    """Evaluates reranked search results against institutional confidence thresholds
    using a calibrated three-tier gate:
    - Tier 1 (High >= 0.65): Full grounded answer.
    - Tier 2 (Medium 0.40 - 0.65): Grounded answer with caveat warning.
    - Tier 3 (Low < 0.40): Abstain safely with official fallback message.
    """

    HIGH_CONFIDENCE_THRESHOLD: float = 0.75
    MEDIUM_CONFIDENCE_THRESHOLD: float = 0.40
    DEFAULT_FALLBACK_MESSAGE: str = (
        "I don't have verified information on this topic in the official college circulars or notices. "
        "Please check with the relevant department office or visit the official college website."
    )

    def fallback_response(self) -> str:
        """Return the standard fallback message when confidence is insufficient."""
        return self.DEFAULT_FALLBACK_MESSAGE

    DEFAULT_CAVEAT_MESSAGE: str = (
        "Note: This information is derived from related college notices. "
        "Please verify specific dates or fee amounts with the relevant department office."
    )

    def __init__(self, threshold: float | None = None) -> None:
        settings = get_settings()
        raw_val = (
            threshold
            if threshold is not None
            else getattr(settings, "CONFIDENCE_THRESHOLD", self.MEDIUM_CONFIDENCE_THRESHOLD)
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
        """Evaluate a ranked sequence of retrieved chunks against the calibrated 3-tier gate.

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
                caveat=None,
            )

        top_chunk = chunks[0]
        top_score = float(
            top_chunk.rerank_score if top_chunk.rerank_score is not None else top_chunk.score
        )
        confidence_level = self.classify_confidence_level(top_score)

        # Tier 3 Gate Check: Does the highest-scoring chunk meet the abstain threshold?
        if top_score < active_threshold:
            logger.warning(
                f"Confidence gate FAIL: Top score ({top_score:.4f}) is below abstain threshold ({active_threshold:.4f}). "
                f"Triggering fallback message per PRD FR-15."
            )
            return ConfidenceGateResult(
                passed=False,
                top_score=top_score,
                confidence_level=ConfidenceLevel.LOW,
                fallback_message=self.generate_fallback_message(top_chunk.department),
                qualifying_chunks=[],
                caveat=None,
            )

        # Filter qualifying chunks: only return chunks that meet threshold
        qualifying = [
            chunk
            for chunk in chunks
            if (chunk.rerank_score if chunk.rerank_score is not None else chunk.score)
            >= active_threshold
        ]

        # Tier 2 Caveat
        caveat = self.DEFAULT_CAVEAT_MESSAGE if confidence_level == ConfidenceLevel.MEDIUM else None

        logger.info(
            f"Confidence gate PASS: Top score is {top_score:.4f} (tier: {confidence_level.value}). "
            f"{len(qualifying)} qualifying chunks passed."
        )

        return ConfidenceGateResult(
            passed=True,
            top_score=top_score,
            confidence_level=confidence_level,
            fallback_message=None,
            qualifying_chunks=qualifying,
            caveat=caveat,
        )
