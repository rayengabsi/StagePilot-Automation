from __future__ import annotations

from app.config.matching import MatchingConfig
from app.domain.recommendation.aggregator import ScoreAggregator
from app.domain.recommendation.entities import ScoreBreakdown


def test_aggregate_all_zero() -> None:
    config = MatchingConfig(
        weights={"skills": 35.0, "technologies": 20.0},
        thresholds={},
        hard_rules={},
        fuzz_threshold=60,
    )
    agg = ScoreAggregator(config)
    score = agg.aggregate(ScoreBreakdown())
    assert score == 0.0


def _full_weights() -> dict[str, float]:
    return {
        "skills": 35.0, "technologies": 20.0, "education": 10.0,
        "experience": 10.0, "languages": 5.0, "projects": 5.0,
        "location": 10.0, "preferences": 5.0,
    }


def test_aggregate_perfect_score() -> None:
    config = MatchingConfig(
        weights=_full_weights(),
        thresholds={},
        hard_rules={},
        fuzz_threshold=60,
    )
    agg = ScoreAggregator(config)
    score = agg.aggregate(ScoreBreakdown(
        skills=100.0, technologies=100.0, education=100.0, experience=100.0,
        languages=100.0, projects=100.0, location=100.0, preferences=100.0,
    ))
    assert score == 100.0


def test_aggregate_partial() -> None:
    config = MatchingConfig(
        weights={"skills": 50.0, "location": 50.0},
        thresholds={},
        hard_rules={},
        fuzz_threshold=60,
    )
    agg = ScoreAggregator(config)
    score = agg.aggregate(ScoreBreakdown(skills=80.0, location=40.0))
    assert score == 60.0


def test_weights_sum_to_zero() -> None:
    config = MatchingConfig(
        weights={},
        thresholds={},
        hard_rules={},
        fuzz_threshold=60,
    )
    agg = ScoreAggregator(config)
    score = agg.aggregate(ScoreBreakdown(skills=100.0))
    assert score == 0.0


def test_aggregate_default_weights() -> None:
    config = MatchingConfig(
        weights=_full_weights(),
        thresholds={},
        hard_rules={},
        fuzz_threshold=60,
    )
    agg = ScoreAggregator(config)
    score = agg.aggregate(ScoreBreakdown(skills=100.0))
    expected = (100.0 * 35.0) / 100.0
    assert score == expected
