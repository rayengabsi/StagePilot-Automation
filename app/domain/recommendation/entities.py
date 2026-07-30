from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.recommendation.enums import FeedbackReason, RecommendationStatus


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
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class RecommendationFeedback:
    recommendation_id: int
    reason: FeedbackReason
    comment: str | None = None
    created_at: str | None = None
