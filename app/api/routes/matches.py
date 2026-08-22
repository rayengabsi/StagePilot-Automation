"""GET /api/matches — recent job recommendations / matches."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import MatchListResponse, MatchResponse
from app.db.models.jobs import Job
from app.db.models.recommendation import RecommendationRecord

router = APIRouter()

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@router.get("/api/matches", response_model=MatchListResponse, tags=["matches"])
def list_matches(
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),  # noqa: B008
) -> MatchListResponse:
    """Return recommendations with their associated job info."""
    total: int = session.scalar(func.count().select().select_from(RecommendationRecord)) or 0
    rows = (
        session.query(RecommendationRecord, Job)
        .join(Job, RecommendationRecord.job_id == Job.id, isouter=True)
        .order_by(RecommendationRecord.created_at.desc(), RecommendationRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return MatchListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_match_to_response(rec, job) for rec, job in rows],
    )


def _match_to_response(rec: RecommendationRecord, job: Job | None) -> MatchResponse:
    return MatchResponse(
        id=rec.id,
        job_id=rec.job_id,
        job_title=job.title if job else "",
        job_company=job.company if job else None,
        job_url=job.url if job else "",
        final_score=rec.final_score,
        ranking_position=rec.ranking_position,
        status=rec.status,
        matched_skills=rec.matched_skills_json or [],
        missing_skills=rec.missing_skills_json or [],
        matched_technologies=rec.matched_technologies_json or [],
        missing_technologies=rec.missing_technologies_json or [],
        explanation=(rec.insights_json or {}).get("explanation", "")
        if isinstance(rec.insights_json, dict)
        else "",
        hard_rule_passed=rec.hard_rule_passed,
        created_at=rec.created_at,
    )
