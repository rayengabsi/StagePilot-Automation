"""Build LinkedIn search keywords and filters from the master career profile.

Keeps the real LinkedIn connector from searching every job on LinkedIn. Uses
the profile's preferred technologies, preferred countries, remote preference
and internship seeking preference to derive focused ``search_jobs`` arguments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.master_profile.entities import MasterProfile
from app.domain.master_profile.enums import InternshipDuration, RemotePreference


@dataclass(frozen=True, slots=True)
class LinkedInSearchQuery:
    """Focused search arguments for the LinkedIn ``search_jobs`` tool."""

    keywords: str
    location: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    work_type: str | None = None

    def to_config(self) -> dict[str, Any]:
        """Return the search filters to merge into a source configuration."""
        result: dict[str, Any] = {"keywords": self.keywords}
        for key in ("location", "job_type", "experience_level", "work_type"):
            value = getattr(self, key)
            if value:
                result[key] = value
        return result


def build_linkedin_search_query(profile: MasterProfile) -> LinkedInSearchQuery:
    """Derive a focused LinkedIn search query from the master profile."""
    preferences = profile.preferences

    technologies = list(dict.fromkeys(preferences.preferred_technologies or ()))
    if not technologies:
        technologies = [skill.name for skill in profile.skills if skill.name][:4]

    tech_terms = technologies[:4]
    keywords = " ".join(term for term in tech_terms if term)

    internship = preferences.internship_duration != InternshipDuration.ANY
    if internship:
        suffix = keywords or "apprenticeship"
        keywords = f"{suffix} internship"
        job_type = "internship,full_time"
        experience_level = "internship"
    else:
        job_type = "full_time"
        experience_level = None

    location = _location_clause(preferences.preferred_countries, preferences.preferred_cities)
    work_type = _work_type_for(preferences.remote_preference)

    return LinkedInSearchQuery(
        keywords=keywords.strip() or "software development",
        location=location,
        job_type=job_type,
        experience_level=experience_level,
        work_type=work_type,
    )


def _location_clause(countries: tuple[str, ...], cities: tuple[str, ...]) -> str | None:
    if cities:
        return ", ".join(cities[:3])
    if countries:
        return ", ".join(countries[:3])
    return None


def _work_type_for(preference: RemotePreference) -> str | None:
    mapping: dict[RemotePreference, str | None] = {
        RemotePreference.REMOTE: "remote",
        RemotePreference.HYBRID: "hybrid",
        RemotePreference.ONSITE: "on_site",
        RemotePreference.ANY: None,
    }
    return mapping.get(preference)
