from __future__ import annotations

from app.domain.recommendation.entities import (
    HardRuleResult,
    MatchedDetail,
    Recommendation,
    RecommendationInsights,
    ScoreBreakdown,
    WeightedBreakdown,
    WeightedComponent,
)
from app.domain.recommendation.enums import ConfidenceLevel, RecommendationStatus


def test_score_breakdown_new_fields_default_to_zero() -> None:
    breakdown = ScoreBreakdown()
    assert breakdown.classification == 0.0
    assert breakdown.remote == 0.0
    assert breakdown.seniority == 0.0
    assert breakdown.hard_filters == 0.0
    assert breakdown.ai == 0.0


def test_score_breakdown_to_dict_includes_intelligence_categories() -> None:
    data = ScoreBreakdown().to_dict()
    for category in (
        "classification",
        "remote",
        "seniority",
        "hard_filters",
        "ai",
    ):
        assert category in data
    assert data["classification"] == 0.0


def test_weighted_component_to_dict() -> None:
    comp = WeightedComponent(
        category="skills", score=80.0, weight=35.0, weighted_score=2800.0, contribution=20.74
    )
    data = comp.to_dict()
    assert data["category"] == "skills"
    assert data["score"] == 80.0


def test_weighted_breakdown_component_lookup() -> None:
    breakdown = WeightedBreakdown(
        final_score=50.0,
        total_weight=100.0,
        components=(
            WeightedComponent("skills", 50.0, 35.0, 1750.0, 17.5),
            WeightedComponent("location", 100.0, 10.0, 1000.0, 10.0),
        ),
    )
    assert breakdown.component("skills") is not None
    assert breakdown.component("location").score == 100.0
    assert breakdown.component("nope") is None


def test_weighted_breakdown_to_dict() -> None:
    breakdown = WeightedBreakdown(
        final_score=50.0,
        total_weight=100.0,
        components=(WeightedComponent("skills", 50.0, 35.0, 1750.0, 17.5),),
    )
    data = breakdown.to_dict()
    assert data["final_score"] == 50.0
    assert data["components"][0]["category"] == "skills"


def test_insights_defaults() -> None:
    insights = RecommendationInsights()
    assert insights.confidence == ConfidenceLevel.LOW
    assert insights.reasons == ()
    assert insights.summary == ""
    assert insights.ai_contribution == 0.0


def test_insights_to_dict() -> None:
    insights = RecommendationInsights(
        confidence=ConfidenceLevel.HIGH,
        reasons=("Strong Python match", "Missing Docker experience"),
        summary="Strong Python match. Missing Docker experience.",
        ai_contribution=5.0,
    )
    data = insights.to_dict()
    assert data["confidence"] == "high"
    assert data["reasons"] == ["Strong Python match", "Missing Docker experience"]
    assert data["ai_contribution"] == 5.0


def test_recommendation_backward_compatible_construction() -> None:
    """Recommendation without the new fields must still build (API stability)."""
    rec = Recommendation(
        profile_id=1,
        job_id=2,
        final_score=80.0,
        ranking_position=1,
        status=RecommendationStatus.ACTIVE,
        matched_detail=MatchedDetail(),
        score_breakdown=ScoreBreakdown(),
        hard_rule_result=HardRuleResult(passed=True),
    )
    assert rec.weighted_breakdown is None
    assert rec.insights is None
    data = rec.to_dict()
    assert data["weighted_breakdown"] is None
    assert data["insights"] is None


def test_recommendation_to_dict_includes_intelligence() -> None:
    rec = Recommendation(
        profile_id=1,
        job_id=2,
        final_score=80.0,
        ranking_position=1,
        status=RecommendationStatus.ACTIVE,
        matched_detail=MatchedDetail(matched_skills=("Python",)),
        score_breakdown=ScoreBreakdown(skills=100.0),
        hard_rule_result=HardRuleResult(passed=True),
        weighted_breakdown=WeightedBreakdown(
            final_score=80.0,
            total_weight=100.0,
            components=(WeightedComponent("skills", 100.0, 35.0, 3500.0, 35.0),),
        ),
        insights=RecommendationInsights(
            confidence=ConfidenceLevel.VERY_HIGH,
            reasons=("Strong Python match",),
            summary="Strong Python match.",
        ),
    )
    data = rec.to_dict()
    assert data["weighted_breakdown"]["final_score"] == 80.0
    assert data["insights"]["confidence"] == "very_high"
    assert data["insights"]["summary"] == "Strong Python match."
