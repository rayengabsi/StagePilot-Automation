"""Standardised JSON error responses for the StagePilot API."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


async def api_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Catch-all handler: never expose secrets, stack traces, or SQL."""
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
    )


class APIError(Exception):
    """Structured API error with a code and HTTP status."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


async def api_domain_error_handler(_request: Request, exc: APIError) -> JSONResponse:
    """Return structured domain errors without leaking internals."""
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
