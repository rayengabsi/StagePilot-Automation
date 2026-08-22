"""GET /api/scheduler/status — scheduler state snapshot."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import SchedulerStatusResponse
from app.services.scheduler_service import SchedulerService

router = APIRouter()


@router.get(
    "/api/scheduler/status",
    response_model=SchedulerStatusResponse,
    tags=["scheduler"],
)
def get_scheduler_status() -> SchedulerStatusResponse:
    """Report the scheduler configuration and last-run state."""
    svc = SchedulerService()
    return SchedulerStatusResponse(**svc.status_snapshot())
