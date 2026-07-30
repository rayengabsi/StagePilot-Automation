from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.config.settings import FilterRules
from app.db.models.jobs import Job
from app.domain.matching.entities import FilterResult, RejectionReason
from app.domain.matching.enums import RejectionCategory


class HardFilterService:
    """Apply deterministic hard filters to a single normalized job."""

    def __init__(self, rules: FilterRules) -> None:
        """Initialize the service with configurable filter rules."""
        self._rules = rules

    def evaluate(self, job: Job, session: Session | None = None) -> FilterResult:
        """Run all hard filters and return a structured result.

        The session parameter is accepted for future database-backed rule
        resolution without changing the public contract.
        """
        _ = session
        title = (job.title or "").lower()
        description = ((job.description or "") + " " + (job.requirements or "")).lower()
        combined = title + " " + description
        location = (job.location or "").lower()

        reasons: list[RejectionReason] = []
        reasons.extend(self._check_pfe(combined))
        reasons.extend(self._check_location(location))
        reasons.extend(self._check_seniority(title, description))
        reasons.extend(self._check_cs_field(combined))
        reasons.extend(self._check_employment_type(combined))
        return FilterResult(passed=len(reasons) == 0, rejection_reasons=tuple(reasons))

    def _keyword_in_text(self, text: str, keywords: list[str]) -> list[str]:
        """Return matched keywords found in text using word-boundary matching."""
        found: list[str] = []
        for keyword in keywords:
            pattern = re.compile(r"(?<![a-z])" + re.escape(keyword.lower()) + r"(?![a-z])")
            if pattern.search(text):
                found.append(keyword)
        return found

    def _check_pfe(self, combined: str) -> list[RejectionReason]:
        """Reject if the job has no PFE or internship signals."""
        positives = self._keyword_in_text(combined, self._rules.pfe_keywords)
        negatives = self._keyword_in_text(combined, self._rules.employment_type_blacklist)
        if negatives and not positives:
            return [
                RejectionReason(
                    category=RejectionCategory.NOT_PFE,
                    detail="Employment type suggests a full-time role, not an internship.",
                    matched_keyword=negatives[0],
                )
            ]
        return []

    def _check_location(self, location: str) -> list[RejectionReason]:
        """Reject if the location is explicitly blacklisted or not whitelisted."""
        blacklisted = self._keyword_in_text(location, self._rules.location_blacklist)
        if blacklisted:
            return [
                RejectionReason(
                    category=RejectionCategory.LOCATION_MISMATCH,
                    detail=f"Location is in the blacklist: {blacklisted[0]}.",
                    matched_keyword=blacklisted[0],
                )
            ]
        whitelisted = self._keyword_in_text(location, self._rules.location_whitelist)
        if not whitelisted and location:
            remote_keywords = self._keyword_in_text(
                location, self._rules.remote_keywords.get("remote", [])
            )
            if not remote_keywords:
                return [
                    RejectionReason(
                        category=RejectionCategory.LOCATION_MISMATCH,
                        detail=f"Location not in whitelist: {location}.",
                        matched_keyword=None,
                    )
                ]
        return []

    def _check_seniority(self, title: str, description: str) -> list[RejectionReason]:
        """Reject if the title or description indicates a senior-level role."""
        title_matches = self._keyword_in_text(title, self._rules.seniority_blacklist)
        if not title_matches:
            desc_matches = self._keyword_in_text(description, self._rules.seniority_blacklist)
            if desc_matches:
                title_matches = desc_matches
        if title_matches:
            return [
                RejectionReason(
                    category=RejectionCategory.SENIORITY_TOO_HIGH,
                    detail=f"Role appears senior-level: {title_matches[0]}.",
                    matched_keyword=title_matches[0],
                )
            ]
        return []

    def _check_cs_field(self, combined: str) -> list[RejectionReason]:
        """Reject if the job does not appear to be in a computer-science field."""
        matches = self._keyword_in_text(combined, self._rules.cs_field_keywords)
        if not matches:
            return [
                RejectionReason(
                    category=RejectionCategory.NOT_CS_FIELD,
                    detail="No computer-science or software keywords found.",
                    matched_keyword=None,
                )
            ]
        return []

    def _check_employment_type(self, combined: str) -> list[RejectionReason]:
        """Reject if explicit employment-type keywords suggest a non-internship role."""
        blacklisted = self._keyword_in_text(combined, self._rules.employment_type_blacklist)
        whitelisted = self._keyword_in_text(combined, self._rules.employment_type_keywords)
        if blacklisted and not whitelisted:
            return [
                RejectionReason(
                    category=RejectionCategory.EMPLOYMENT_TYPE,
                    detail=f"Employment type appears to be a full-time role: {blacklisted[0]}.",
                    matched_keyword=blacklisted[0],
                )
            ]
        return []
