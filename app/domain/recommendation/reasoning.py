from __future__ import annotations

from datetime import date

from app.db.models.jobs import Job
from app.domain.master_profile.entities import MasterProfile
from app.domain.recommendation.entities import (
    HardRuleResult,
    MatchedDetail,
    ScoreBreakdown,
)

_SENIORITY_YEARS: dict[str, tuple[float, float]] = {
    "intern": (0.0, 1.0),
    "junior": (0.0, 2.0),
    "mid": (2.0, 6.0),
    "senior": (5.0, 15.0),
    "lead": (6.0, 15.0),
    "manager": (6.0, 20.0),
    "director": (8.0, 30.0),
}


class ReasoningBuilder:
    """Build deterministic, human-readable explanations for a recommendation.

    Every statement is derived from structured match data only — no AI and no
    free text. ``build`` returns a tuple of short reasons plus a composed
    one-line summary.
    """

    def build(
        self,
        profile: MasterProfile,
        job: Job,
        breakdown: ScoreBreakdown,
        matched: MatchedDetail,
        hard_rule_result: HardRuleResult | None = None,
    ) -> tuple[tuple[str, ...], str]:
        """Return (reasons, summary) for a recommendation."""
        if hard_rule_result is not None and not hard_rule_result.passed:
            reasons = list(hard_rule_result.reasons)
            return tuple(reasons), _summarize(reasons)

        reasons: list[str] = []
        reasons.extend(self._skills_reasons(matched, breakdown))
        reasons.extend(self._missing_reasons(matched))
        reasons.extend(self._location_reasons(job, breakdown))
        reasons.extend(self._remote_reasons(profile, job, breakdown))
        reasons.extend(self._seniority_reasons(profile, job))
        reasons.extend(self._education_reasons(profile, breakdown))

        return tuple(reasons), _summarize(reasons)

    @staticmethod
    def _skills_reasons(matched: MatchedDetail, breakdown: ScoreBreakdown) -> list[str]:
        items = _merge(matched.matched_skills, matched.matched_technologies)
        if not items:
            return []
        items = items[:3]
        if breakdown.skills >= 60.0 or breakdown.technologies >= 60.0:
            return [f"Strong {_join_terms(items)} match"]
        return [f"Partial {_join_terms(items)} match"]

    @staticmethod
    def _missing_reasons(matched: MatchedDetail) -> list[str]:
        reasons: list[str] = []
        techs = list(matched.missing_technologies)[:2]
        if techs:
            reasons.append(f"Missing {_join_terms(techs)} experience")
        skills = list(matched.missing_skills)[:2]
        if skills:
            reasons.append(f"Missing {_join_terms(skills)}")
        return reasons

    @staticmethod
    def _location_reasons(job: Job, breakdown: ScoreBreakdown) -> list[str]:
        if not (job.location or "").strip():
            return []
        if breakdown.location >= 100.0:
            return ["Location compatible"]
        if breakdown.location > 0.0:
            return ["Partial location match"]
        return ["Location mismatch"]

    @staticmethod
    def _remote_reasons(
        profile: MasterProfile,
        job: Job,
        breakdown: ScoreBreakdown,
    ) -> list[str]:
        pref = profile.preferences.remote_preference
        if pref.value == "any":
            return []
        mode = job.classification_work_mode
        if mode is None:
            if breakdown.remote >= 80.0:
                return ["Remote-friendly role"]
            if breakdown.remote <= 40.0:
                return ["Not remote-friendly"]
            return []
        if mode == "remote":
            if pref.value == "onsite":
                return ["Remote role conflicts with onsite preference"]
            return ["Remote-friendly role"]
        if mode == "hybrid":
            if pref.value == "onsite":
                return ["Hybrid role conflicts with onsite preference"]
            return ["Hybrid-friendly role"]
        if mode == "onsite":
            if pref.value == "remote":
                return ["On-site role conflicts with remote preference"]
            if pref.value == "hybrid":
                return ["On-site role conflicts with hybrid preference"]
            return ["On-site role matches preference"]
        return []

    @staticmethod
    def _seniority_reasons(profile: MasterProfile, job: Job) -> list[str]:
        level = job.classification_seniority
        if not level or level not in _SENIORITY_YEARS:
            return []
        years = _total_experience_years(profile)
        lo, hi = _SENIORITY_YEARS[level]
        if years < lo:
            return ["Role may exceed current experience level"]
        if years > hi:
            return ["Role may be below experience level"]
        return ["Seniority aligned"]

    @staticmethod
    def _education_reasons(profile: MasterProfile, breakdown: ScoreBreakdown) -> list[str]:
        if not profile.education:
            return []
        if breakdown.education >= 80.0:
            return ["Education aligns"]
        if breakdown.education <= 20.0:
            return ["Education may not align"]
        return []


def _total_experience_years(profile: MasterProfile) -> float:
    """Total years of experience derived from experience date ranges."""
    today = date.today()
    total_days = 0.0
    for exp in profile.experience:
        start = exp.start_date
        end = exp.end_date if not exp.is_current else today
        if start and end and end >= start:
            total_days += (end - start).days
    return total_days / 365.25


def _merge(*groups: tuple[str, ...]) -> list[str]:
    seen: list[str] = []
    for group in groups:
        for item in group:
            if item not in seen:
                seen.append(item)
    return seen


def _join_terms(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _summarize(reasons: list[str]) -> str:
    if not reasons:
        return "No strong signals detected"
    return ".".join(reasons) + "."
