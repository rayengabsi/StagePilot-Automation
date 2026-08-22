"""GET/PUT /api/filters — job filter configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import FiltersResponse
from app.services.user_filter_service import load_job_filter_rules, save_job_filter_rules

router = APIRouter()


class FiltersUpdateRequest(BaseModel):
    """Partial or full filter rules update."""

    model_config = ConfigDict(from_attributes=True)

    excluded_keywords: list[str] | None = None
    required_keywords: list[str] | None = None
    excluded_titles: list[str] | None = None
    required_titles: list[str] | None = None
    excluded_companies: list[str] | None = None
    required_companies: list[str] | None = None
    excluded_locations: list[str] | None = None
    required_locations: list[str] | None = None
    remote_only: bool | None = None
    employment_type_exclude: list[str] | None = None
    employment_type_include: list[str] | None = None
    seniority_exclude: list[str] | None = None
    seniority_include: list[str] | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    visa_required_keywords: list[str] | None = None
    visa_excluded_keywords: list[str] | None = None
    excluded_sources: list[str] | None = None
    included_sources: list[str] | None = None
    max_job_age_days: int | None = None
    unknown_data_policy: str | None = None


@router.get("/api/filters", response_model=FiltersResponse, tags=["filters"])
def get_filters(session: Session = Depends(get_db)) -> FiltersResponse:  # noqa: B008
    """Return the persisted user filter rules as JSON."""
    rules = load_job_filter_rules(session)
    return FiltersResponse(**rules.model_dump())


@router.put("/api/filters", response_model=FiltersResponse, tags=["filters"])
def update_filters(
    body: FiltersUpdateRequest,
    session: Session = Depends(get_db),  # noqa: B008
) -> FiltersResponse:
    """Replace the persisted user filter rules.

    Accepts the full set of filter fields.  Only supplied (non-None) fields
    override the current configuration — missing fields keep their existing
    values.
    """
    current = load_job_filter_rules(session)
    updates = body.model_dump(exclude_none=True)
    merged = current.model_copy(update=updates)
    save_job_filter_rules(session, merged)
    return FiltersResponse(**merged.model_dump())
