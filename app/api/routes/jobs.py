"""GET /api/jobs — recently discovered jobs with pagination."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import JobListResponse, JobResponse
from app.db.models.jobs import Job

router = APIRouter()

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@router.get("/api/jobs", response_model=JobListResponse, tags=["jobs"])
def list_jobs(
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),  # noqa: B008
) -> JobListResponse:
    """Return recently discovered jobs, newest first."""
    total: int = session.scalar(_select_count()) or 0
    rows = (
        session.query(Job)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return JobListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_job_to_response(j) for j in rows],
    )


def _select_count() -> Select:
    """Return a count expression over all jobs."""
    return func.count().select().select_from(Job)


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        employment_type=job.employment_type,
        seniority=job.classification_seniority,
        remote_status=job.remote_status,
        posted_at=job.posted_at,
        source_id=job.source_id,
        created_at=job.created_at,
    )
