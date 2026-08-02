from __future__ import annotations

from collections.abc import Sequence

from app.domain.recommendation.enums import ConfidenceLevel


class ConfidenceCalculator:
    """Derive recommendation confidence levels from a score distribution.

    Confidence is NOT read off fixed score thresholds. Instead each final score
    is positioned within the distribution of all final scores produced by the
    same recommendation run:

    - the top 25% of the observed score range -> ``VERY_HIGH``
    - the next 25% -> ``HIGH``
    - the next 25% -> ``MEDIUM``
    - the bottom 25% -> ``LOW``

    When every score in the run is identical there is no spread to derive a
    distribution from, so the score's magnitude is used as a documented
    fallback so a low isolated score never reads as a very high confidence.
    """

    @classmethod
    def assign(cls, scores: Sequence[float]) -> dict[float, ConfidenceLevel]:
        """Map each distinct final score to a confidence level."""
        if not scores:
            return {}
        lo, hi = min(scores), max(scores)
        return {score: cls._level(score, lo, hi) for score in sorted(set(scores), reverse=True)}

    @classmethod
    def level_for(cls, score: float, scores: Sequence[float]) -> ConfidenceLevel:
        """Return the confidence level for a single score within a run."""
        if not scores:
            return cls._magnitude(score)
        return cls._level(score, min(scores), max(scores))

    @classmethod
    def _level(cls, score: float, lo: float, hi: float) -> ConfidenceLevel:
        if hi == lo:
            return cls._magnitude(score)
        position = (score - lo) / (hi - lo)
        if position >= 0.75:
            return ConfidenceLevel.VERY_HIGH
        if position >= 0.50:
            return ConfidenceLevel.HIGH
        if position >= 0.25:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    @staticmethod
    def _magnitude(score: float) -> ConfidenceLevel:
        if score >= 80.0:
            return ConfidenceLevel.VERY_HIGH
        if score >= 60.0:
            return ConfidenceLevel.HIGH
        if score >= 40.0:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
