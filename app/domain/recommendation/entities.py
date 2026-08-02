from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.recommendation.enums import (
    ConfidenceLevel,
    FeedbackReason,
    RecommendationStatus,
)


@dataclass(frozen=True, slots=True)
class HardRuleResult:
    passed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    skills: float = 0.0
    technologies: float = 0.0
    education: float = 0.0
    experience: float = 0.0
    languages: float = 0.0
    projects: float = 0.0
    location: float = 0.0
    preferences: float = 0.0
    classification: float = 0.0
    remote: float = 0.0
    seniority: float = 0.0
    hard_filters: float = 0.0
    ai: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "skills": self.skills,
            "technologies": self.technologies,
            "education": self.education,
            "experience": self.experience,
            "languages": self.languages,
            "projects": self.projects,
            "location": self.location,
            "preferences": self.preferences,
            "classification": self.classification,
            "remote": self.remote,
            "seniority": self.seniority,
            "hard_filters": self.hard_filters,
            "ai": self.ai,
        }


@dataclass(frozen=True, slots=True)
class WeightedComponent:
    """One category's weighted contribution to the final score."""

    category: str
    score: float
    weight: float
    weighted_score: float
    contribution: float

    def to_dict(self) -> dict[str, float | str]:
        return {
            "category": self.category,
            "score": self.score,
            "weight": self.weight,
            "weighted_score": self.weighted_score,
            "contribution": self.contribution,
        }


@dataclass(frozen=True, slots=True)
class WeightedBreakdown:
    """The final score plus every weighted component that produced it."""

    final_score: float
    total_weight: float
    components: tuple[WeightedComponent, ...] = ()

    def component(self, category: str) -> WeightedComponent | None:
        """Return the weighted component for a category, or None."""
        for comp in self.components:
            if comp.category == category:
                return comp
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_score": self.final_score,
            "total_weight": self.total_weight,
            "components": [c.to_dict() for c in self.components],
        }


@dataclass(frozen=True, slots=True)
class MatchedDetail:
    matched_skills: tuple[str, ...] = ()
    missing_skills: tuple[str, ...] = ()
    matched_technologies: tuple[str, ...] = ()
    missing_technologies: tuple[str, ...] = ()
    matched_preferences: tuple[str, ...] = ()
    unmatched_preferences: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "matched_skills": list(self.matched_skills),
            "missing_skills": list(self.missing_skills),
            "matched_technologies": list(self.matched_technologies),
            "missing_technologies": list(self.missing_technologies),
            "matched_preferences": list(self.matched_preferences),
            "unmatched_preferences": list(self.unmatched_preferences),
        }


@dataclass(frozen=True, slots=True)
class RecommendationInsights:
    """Explainability metadata for a recommendation.

    ``confidence`` is derived from the score distribution of the run it was
    produced in. ``reasons`` are deterministic, human-readable explanations of
    why the recommendation scored the way it did. ``ai_contribution`` records a
    numeric AI contribution when AI participates in scoring (0.0 otherwise).
    """

    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    reasons: tuple[str, ...] = ()
    summary: str = ""
    ai_contribution: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence.value,
            "reasons": list(self.reasons),
            "summary": self.summary,
            "ai_contribution": self.ai_contribution,
        }


@dataclass(frozen=True, slots=True)
class Recommendation:
    profile_id: int
    job_id: int
    final_score: float
    ranking_position: int
    status: RecommendationStatus
    matched_detail: MatchedDetail
    score_breakdown: ScoreBreakdown
    hard_rule_result: HardRuleResult
    created_at: str = ""
    weighted_breakdown: WeightedBreakdown | None = None
    insights: RecommendationInsights | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "job_id": self.job_id,
            "final_score": self.final_score,
            "ranking_position": self.ranking_position,
            "status": self.status.value,
            "matched_detail": self.matched_detail.to_dict(),
            "score_breakdown": self.score_breakdown.to_dict(),
            "hard_rule_passed": self.hard_rule_result.passed,
            "hard_rule_reasons": list(self.hard_rule_result.reasons),
            "weighted_breakdown": (
                self.weighted_breakdown.to_dict() if self.weighted_breakdown else None
            ),
            "insights": self.insights.to_dict() if self.insights else None,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class RecommendationFeedback:
    recommendation_id: int
    reason: FeedbackReason
    comment: str | None = None
    created_at: str | None = None
