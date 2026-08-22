"""GET /api/health — liveness probe."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    """Verify the API process is alive.

    Does **not** perform expensive LinkedIn/DB checks.
    """
    return HealthResponse(status="ok")
