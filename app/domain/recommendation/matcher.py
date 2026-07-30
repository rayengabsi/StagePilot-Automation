from __future__ import annotations

from app.config.matching import MatchingConfig
from app.db.models.jobs import Job
from app.domain.master_profile.entities import MasterProfile
from app.domain.master_profile.enums import RemotePreference
from app.domain.recommendation.entities import HardRuleResult


class HardRuleMatcher:
    """Evaluate mandatory constraints between a profile and a job.

    Hard-rule failures reject the recommendation before similarity scoring.
    """

    def __init__(self, config: MatchingConfig) -> None:
        self._config = config

    @staticmethod
    def _job_text(job: Job) -> str:
        parts = [job.title or "", job.description or "", job.requirements or ""]
        return " ".join(parts).lower()

    def evaluate(self, profile: MasterProfile, job: Job) -> HardRuleResult:
        reasons: list[str] = []

        if self._config.hard_rules.get("match_country", False):
            reason = self._check_country(profile, job)
            if reason:
                reasons.append(reason)

        if self._config.hard_rules.get("match_work_mode", False):
            reason = self._check_work_mode(profile, job)
            if reason:
                reasons.append(reason)

        if self._config.hard_rules.get("match_language", False):
            reason = self._check_language(profile, job)
            if reason:
                reasons.append(reason)

        return HardRuleResult(passed=not reasons, reasons=tuple(reasons))

    def _check_country(self, profile: MasterProfile, job: Job) -> str | None:
        preferred = profile.preferences.preferred_countries
        if not preferred:
            return None
        job_location = (job.location or "").lower()
        if not job_location:
            return None
        for country in preferred:
            if country.lower() in job_location:
                return None
        preferred_str = ", ".join(preferred)
        return f"Job location '{job.location}' does not match preferred countries: {preferred_str}"

    def _check_work_mode(self, profile: MasterProfile, job: Job) -> str | None:
        pref = profile.preferences.remote_preference
        if pref == RemotePreference.ANY:
            return None
        job_text = self._job_text(job)
        remote_kw = ["remote", "teletravail", "work from home", "distantiel"]
        if pref == RemotePreference.REMOTE and not any(kw in job_text for kw in remote_kw):
            return "Job does not appear to support remote work"
        onsite_kw = ["remote", "teletravail", "work from home"]
        if pref == RemotePreference.ONSITE and any(kw in job_text for kw in onsite_kw):
            return "Job is remote but profile prefers onsite"
        return None

    def _check_language(self, profile: MasterProfile, job: Job) -> str | None:
        preferred_lang = profile.preferences.preferred_language
        if not preferred_lang:
            return None
        job_text = self._job_text(job)
        if preferred_lang.lower() not in job_text:
            return f"Job does not mention preferred language '{preferred_lang}'"
        return None
