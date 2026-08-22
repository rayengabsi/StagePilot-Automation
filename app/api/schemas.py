"""Typed response schemas for the StagePilot API.

These are thin wrappers that document the JSON shape returned by each
endpoint.  They are **not** used to build responses — the routes delegate
to existing services whose ``to_dict()`` / ``model_dump()`` output is
returned directly.  The schemas exist so that FastAPI can render them in
the OpenAPI docs.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Simple liveness probe."""

    model_config = ConfigDict(from_attributes=True)

    status: str = "ok"


# ── Profile ───────────────────────────────────────────────────────────────────


class PersonalInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str = ""
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    nationality: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None


class Education(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    institution: str = ""
    degree: str = ""
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None
    description: str | None = None


class Experience(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company: str = ""
    title: str = ""
    location: str | None = None
    start_date: str = ""
    end_date: str | None = None
    is_current: bool = False
    description: str = ""
    technologies: list[str] = []


class Project(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = ""
    description: str = ""
    url: str | None = None
    technologies: list[str] = []
    start_date: str | None = None
    end_date: str | None = None


class Skill(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = ""
    category: str | None = None
    proficiency: str | None = None


class Language(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = ""
    proficiency: str | None = None


class Certification(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = ""
    issuer: str = ""
    date: str | None = None
    url: str | None = None


class Award(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = ""
    issuer: str = ""
    date: str | None = None
    description: str | None = None


class Publication(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str = ""
    publisher: str | None = None
    date: str | None = None
    url: str | None = None
    description: str | None = None


class Preference(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    countries: list[str] = []
    cities: list[str] = []
    remote_preference: str | None = None
    technologies: list[str] = []
    industries: list[str] = []
    company_size: str | None = None
    language: str | None = None
    salary_expectation: str | None = None


class CompletenessInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float = 0.0
    breakdown: dict[str, float] = {}
    missing_fields: list[str] = []


class ProfileResponse(BaseModel):
    """Full master profile exposed through the API."""

    model_config = ConfigDict(from_attributes=True)

    personal_info: PersonalInfo = PersonalInfo()
    education: list[Education] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    skills: list[Skill] = []
    languages: list[Language] = []
    certifications: list[Certification] = []
    awards: list[Award] = []
    publications: list[Publication] = []
    preferences: Preference = Preference()
    completeness: CompletenessInfo = CompletenessInfo()


# ── Filters ───────────────────────────────────────────────────────────────────


class FiltersResponse(BaseModel):
    """Current job filter configuration (matches JobFilterRules exactly)."""

    model_config = ConfigDict(from_attributes=True)

    excluded_keywords: list[str] = []
    required_keywords: list[str] = []
    excluded_titles: list[str] = []
    required_titles: list[str] = []
    excluded_companies: list[str] = []
    required_companies: list[str] = []
    excluded_locations: list[str] = []
    required_locations: list[str] = []
    remote_only: bool = False
    employment_type_exclude: list[str] = []
    employment_type_include: list[str] = []
    seniority_exclude: list[str] = []
    seniority_include: list[str] = []
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    visa_required_keywords: list[str] = []
    visa_excluded_keywords: list[str] = []
    excluded_sources: list[str] = []
    included_sources: list[str] = []
    max_job_age_days: int | None = None
    unknown_data_policy: str = "accept"


# ── Scheduler ─────────────────────────────────────────────────────────────────


class SchedulerStatusResponse(BaseModel):
    """Scheduler state snapshot."""

    model_config = ConfigDict(from_attributes=True)

    enabled: bool = False
    running: bool = False
    pid: int | None = None
    interval_minutes: int = 30
    started_at: str | None = None
    last_run_status: str | None = None
    last_run_success: bool | None = None
    last_run_at: str | None = None
    last_run_fetched: int | None = None
    next_run_at: str | None = None
    stop_requested: bool = False


# ── Jobs ──────────────────────────────────────────────────────────────────────


class JobResponse(BaseModel):
    """Single job listing from the discovery database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str | None = None
    location: str | None = None
    url: str = ""
    employment_type: str | None = None
    seniority: str | None = None
    remote_status: str | None = None
    posted_at: datetime | None = None
    source_id: int | None = None
    created_at: datetime | None = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    limit: int
    offset: int
    items: list[JobResponse]


# ── Matches ───────────────────────────────────────────────────────────────────


class MatchResponse(BaseModel):
    """A single recommendation / job match."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    job_title: str = ""
    job_company: str | None = None
    job_url: str = ""
    final_score: float = 0.0
    ranking_position: int = 0
    status: str = "active"
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    matched_technologies: list[str] = []
    missing_technologies: list[str] = []
    explanation: str = ""
    hard_rule_passed: bool = True
    created_at: datetime | None = None


class MatchListResponse(BaseModel):
    """Paginated list of matches."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    limit: int
    offset: int
    items: list[MatchResponse]


# ── Errors ────────────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    error: ErrorDetail
