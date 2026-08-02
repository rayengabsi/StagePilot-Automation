from __future__ import annotations

from app.domain.recommendation.confidence import ConfidenceCalculator
from app.domain.recommendation.enums import ConfidenceLevel


def test_distinct_distribution_positions() -> None:
    scores = [20.0, 40.0, 60.0, 80.0, 100.0]
    mapping = ConfidenceCalculator.assign(scores)
    assert mapping[100.0] == ConfidenceLevel.VERY_HIGH
    assert mapping[80.0] == ConfidenceLevel.VERY_HIGH
    assert mapping[60.0] == ConfidenceLevel.HIGH
    assert mapping[40.0] == ConfidenceLevel.MEDIUM
    assert mapping[20.0] == ConfidenceLevel.LOW


def test_clustered_distribution() -> None:
    scores = [30.0, 30.0, 30.0, 90.0]
    mapping = ConfidenceCalculator.assign(scores)
    assert mapping[90.0] == ConfidenceLevel.VERY_HIGH
    assert mapping[30.0] == ConfidenceLevel.LOW


def test_mid_range_distribution() -> None:
    scores = [35.0, 50.0, 65.0]
    mapping = ConfidenceCalculator.assign(scores)
    assert mapping[65.0] == ConfidenceLevel.VERY_HIGH
    assert mapping[50.0] == ConfidenceLevel.HIGH
    assert mapping[35.0] == ConfidenceLevel.LOW


def test_two_score_distribution() -> None:
    scores = [40.0, 80.0]
    mapping = ConfidenceCalculator.assign(scores)
    assert mapping[80.0] == ConfidenceLevel.VERY_HIGH
    assert mapping[40.0] == ConfidenceLevel.LOW


def test_degenerate_single_score_low() -> None:
    """A single low score must not read as high confidence."""
    assert ConfidenceCalculator.level_for(20.0, [20.0]) == ConfidenceLevel.LOW


def test_degenerate_single_score_high() -> None:
    assert ConfidenceCalculator.level_for(70.0, [70.0]) == ConfidenceLevel.HIGH
    assert ConfidenceCalculator.level_for(85.0, [85.0]) == ConfidenceLevel.VERY_HIGH


def test_degenerate_all_equal() -> None:
    mapping = ConfidenceCalculator.assign([50.0, 50.0, 50.0])
    assert mapping[50.0] == ConfidenceLevel.MEDIUM


def test_empty_distribution() -> None:
    assert ConfidenceCalculator.assign([]) == {}
    assert ConfidenceCalculator.level_for(70.0, []) == ConfidenceLevel.HIGH


def test_assign_covers_every_distinct_score() -> None:
    scores = [10.0, 10.0, 55.0, 78.0, 78.0]
    mapping = ConfidenceCalculator.assign(scores)
    assert set(mapping) == {10.0, 55.0, 78.0}


def test_boundary_positions() -> None:
    scores = [0.0, 50.0, 100.0]
    mapping = ConfidenceCalculator.assign(scores)
    assert mapping[100.0] == ConfidenceLevel.VERY_HIGH
    assert mapping[50.0] == ConfidenceLevel.HIGH
    assert mapping[0.0] == ConfidenceLevel.LOW
