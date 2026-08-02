from __future__ import annotations

from app.config.matching import MatchingConfig
from app.domain.recommendation.aggregator import ScoreAggregator
from app.domain.recommendation.entities import ScoreBreakdown


def _full_weights() -> dict[str, float]:
    return {
        "skills": 35.0,
        "technologies": 20.0,
        "education": 10.0,
        "experience": 10.0,
        "languages": 5.0,
        "projects": 5.0,
        "location": 10.0,
        "preferences": 5.0,
        "classification": 15.0,
        "remote": 5.0,
        "seniority": 5.0,
        "hard_filters": 10.0,
        "ai": 0.0,
    }


def _config(weights: dict[str, float] | None = None) -> MatchingConfig:
    return MatchingConfig(
        weights=weights if weights is not None else _full_weights(),
        thresholds={},
        hard_rules={},
        fuzz_threshold=60,
    )


def test_weighted_final_matches_scalar_aggregate() -> None:
    """aggregate_weighted and aggregate must produce the same final score."""
    agg = ScoreAggregator(_config())
    breakdown = ScoreBreakdown(skills=80.0, technologies=40.0, location=100.0)
    assert agg.aggregate(breakdown) == agg.aggregate_weighted(breakdown).final_score


def test_weighted_components_cover_all_configured_categories() -> None:
    agg = ScoreAggregator(_config())
    weighted = agg.aggregate_weighted(ScoreBreakdown(skills=100.0))
    categories = {c.category for c in weighted.components}
    assert categories == set(_full_weights())


def test_weighted_component_calculation() -> None:
    agg = ScoreAggregator(_config())
    weighted = agg.aggregate_weighted(ScoreBreakdown(skills=50.0))
    comp = weighted.component("skills")
    assert comp is not None
    assert comp.score == 50.0
    assert comp.weight == 35.0
    assert comp.weighted_score == 50.0 * 35.0
    assert comp.contribution == 50.0 * 35.0 / 135.0


def test_contributions_reconstruct_final_score() -> None:
    agg = ScoreAggregator(_config())
    breakdown = ScoreBreakdown(
        skills=100.0,
        technologies=80.0,
        education=60.0,
        location=40.0,
        classification=100.0,
        remote=70.0,
        seniority=50.0,
        hard_filters=100.0,
    )
    weighted = agg.aggregate_weighted(breakdown)
    total = sum(c.weighted_score for c in weighted.components)
    assert total / weighted.total_weight == weighted.final_score
    assert abs(sum(c.contribution for c in weighted.components) - weighted.final_score) < 1e-9


def test_new_intelligence_categories_influence_final_score() -> None:
    agg = ScoreAggregator(_config())
    without = agg.aggregate(ScoreBreakdown(skills=100.0))
    with_intel = agg.aggregate(
        ScoreBreakdown(
            skills=100.0,
            classification=100.0,
            remote=100.0,
            seniority=100.0,
            hard_filters=100.0,
        )
    )
    assert with_intel > without


def test_zero_weight_category_contributes_nothing() -> None:
    agg = ScoreAggregator(_config())
    weighted = agg.aggregate_weighted(ScoreBreakdown(ai=100.0))
    comp = weighted.component("ai")
    assert comp is not None
    assert comp.weighted_score == 0.0
    assert comp.contribution == 0.0


def test_unknown_breakdown_category_defaults_to_zero() -> None:
    """Categories missing from the breakdown score 0.0 without crashing."""
    agg = ScoreAggregator(_config())
    score = agg.aggregate(ScoreBreakdown())
    assert score == 0.0


def test_empty_weights() -> None:
    agg = ScoreAggregator(_config(weights={}))
    weighted = agg.aggregate_weighted(ScoreBreakdown(skills=100.0))
    assert weighted.final_score == 0.0
    assert weighted.total_weight == 0.0
    assert weighted.components == ()


def test_component_not_found_returns_none() -> None:
    agg = ScoreAggregator(_config())
    weighted = agg.aggregate_weighted(ScoreBreakdown())
    assert weighted.component("does_not_exist") is None


def test_weighted_breakdown_to_dict_round_trip() -> None:
    agg = ScoreAggregator(_config())
    weighted = agg.aggregate_weighted(ScoreBreakdown(skills=100.0))
    data = weighted.to_dict()
    assert data["final_score"] == weighted.final_score
    assert len(data["components"]) == len(_full_weights())
    assert data["components"][0]["category"] == "skills"
