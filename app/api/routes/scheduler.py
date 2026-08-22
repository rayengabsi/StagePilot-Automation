"""Scheduler control endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

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


@router.post("/api/scheduler/once", tags=["scheduler"])
def run_scheduler_once() -> dict:
    """Execute the LinkedIn notification pipeline exactly once."""
    svc = SchedulerService()
    return svc.run_once()


@router.post("/api/scheduler/stop", tags=["scheduler"])
def stop_scheduler() -> dict:
    """Request a clean shutdown of a running scheduler."""
    svc = SchedulerService()
    return svc.request_stop()


def _start_scheduler_background(interval_minutes: int | None) -> None:
    svc = SchedulerService()
    svc.start(interval_minutes=interval_minutes)


@router.post("/api/scheduler/start", tags=["scheduler"])
def start_scheduler(
    body: dict | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),  # noqa: B008
) -> dict:
    """Start the recurring scheduler in the background.

    ``start()`` is a blocking loop; we run it in a background thread so the
    HTTP response returns immediately.
    """
    minutes = None
    if body:
        minutes = body.get("interval_minutes")
    background_tasks.add_task(_start_scheduler_background, minutes)
    return {"status": "starting", "interval_minutes": minutes}
