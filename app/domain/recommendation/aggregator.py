from __future__ import annotations

from app.config.matching import MatchingConfig
from app.domain.recommendation.entities import (
    ScoreBreakdown,
    WeightedBreakdown,
    WeightedComponent,
)


class ScoreAggregator:
    """Combine per-category similarity scores into a weighted final score.

    ``aggregate`` remains the original scalar entry point for backward
    compatibility; ``aggregate_weighted`` additionally exposes every weighted
    component that produced the final score.
    """

    def __init__(self, config: MatchingConfig) -> None:
        self._weights = config.weights

    def aggregate(self, breakdown: ScoreBreakdown) -> float:
        total_weight = sum(self._weights.values())
        if total_weight == 0:
            return 0.0

        score_map = breakdown.to_dict()
        weighted = sum(score_map.get(cat, 0.0) * weight for cat, weight in self._weights.items())
        return weighted / total_weight

    def aggregate_weighted(self, breakdown: ScoreBreakdown) -> WeightedBreakdown:
        """Return the final score and every weighted component behind it."""
        total_weight = sum(self._weights.values())
        if total_weight == 0:
            return WeightedBreakdown(final_score=0.0, total_weight=0.0)

        score_map = breakdown.to_dict()
        components: list[WeightedComponent] = []
        weighted_total = 0.0
        for category, weight in self._weights.items():
            score = score_map.get(category, 0.0)
            weighted_score = score * weight
            contribution = weighted_score / total_weight
            weighted_total += weighted_score
            components.append(
                WeightedComponent(
                    category=category,
                    score=score,
                    weight=weight,
                    weighted_score=weighted_score,
                    contribution=contribution,
                )
            )

        return WeightedBreakdown(
            final_score=weighted_total / total_weight,
            total_weight=total_weight,
            components=tuple(components),
        )
