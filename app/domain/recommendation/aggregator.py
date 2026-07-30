from __future__ import annotations

from app.config.matching import MatchingConfig
from app.domain.recommendation.entities import ScoreBreakdown


class ScoreAggregator:
    """Combine per-category similarity scores into a weighted final score."""

    def __init__(self, config: MatchingConfig) -> None:
        self._weights = config.weights

    def aggregate(self, breakdown: ScoreBreakdown) -> float:
        total_weight = sum(self._weights.values())
        if total_weight == 0:
            return 0.0

        score_map = breakdown.to_dict()
        weighted = sum(score_map.get(cat, 0.0) * weight for cat, weight in self._weights.items())
        return weighted / total_weight
