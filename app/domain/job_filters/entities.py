from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.job_filters.enums import JobFilterRejectionCode
from pydantic import BaseModel, ConfigDict, Field


class JobFilterRules(BaseModel):
    """User-controlled hard job filters persisted in the database.

    An empty configuration imposes no restrictions: every job inserted during
    a discovery run is eligible for matching. No personal/Rayen-specific values
    are baked into production code — filters are fully user-defined.
    """

    model_config = ConfigDict(extra="forbid")

    excluded_keywords: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    excluded_titles: list[str] = Field(default_factory=list)
    required_titles: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)
    required_companies: list[str] = Field(default_factory=list)
    excluded_locations: list[str] = Field(default_factory=list)
    required_locations: list[str] = Field(default_factory=list)
    remote_only: bool = False
    employment_type_exclude: list[str] = Field(default_factory=list)
    employment_type_include: list[str] = Field(default_factory=list)
    seniority_exclude: list[str] = Field(default_factory=list)
    seniority_include: list[str] = Field(default_factory=list)
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    visa_required_keywords: list[str] = Field(default_factory=list)
    visa_excluded_keywords: list[str] = Field(default_factory=list)
    excluded_sources: list[str] = Field(default_factory=list)
    included_sources: list[str] = Field(default_factory=list)
    max_job_age_days: int | None = None
    unknown_data_policy: Literal["accept", "reject", "ignore"] = "accept"

    def is_empty(self) -> bool:
        """Return True when no rule is configured (no hard restrictions)."""
        return self == type(self)()


@dataclass(frozen=True, slots=True)
class JobFilterRejection:
    """One structured reason why a job was rejected by the user filter."""

    code: JobFilterRejectionCode
    detail: str
    matched_value: str | None = None


@dataclass(frozen=True, slots=True)
class JobFilterResult:
    """Result of applying the user filter to a single job."""

    passed: bool
    rejections: tuple[JobFilterRejection, ...] = ()
