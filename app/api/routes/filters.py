"""GET /api/filters — current job filter configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import FiltersResponse
from app.services.user_filter_service import load_job_filter_rules

router = APIRouter()


@router.get("/api/filters", response_model=FiltersResponse, tags=["filters"])
def get_filters(session: Session = Depends(get_db)) -> FiltersResponse:  # noqa: B008
    """Return the persisted user filter rules as JSON."""
    rules = load_job_filter_rules(session)
    return FiltersResponse(**rules.model_dump())
