"""FastAPI application factory for the StagePilot API.

Usage::

    uvicorn app.api.app:app --reload --port 8000
    # or via the helper CLI:
    uv run stagepilot api --port 8000

The app wires existing StagePilot services through standard FastAPI
dependency injection.  No business logic lives in route handlers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import APIError, api_domain_error_handler, api_error_handler
from app.api.routes import filters, health, jobs, matches, profile, scheduler

_LOCALHOST_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Startup / shutdown hooks are handled by the existing CLI entry points;
    # the API is a thin read-only layer and requires no extra init.
    yield


def create_app() -> FastAPI:
    """Build and configure the StagePilot FastAPI application."""
    application = FastAPI(
        title="StagePilot API",
        description=(
            "Local development API for the StagePilot internship automation "
            "platform.  Exposes read-only endpoints for profile, filters, "
            "scheduler, jobs and matches."
        ),
        version="0.1.0",
        lifespan=_lifespan,
    )

    # CORS — localhost-only during development.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_LOCALHOST_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )

    # Error handlers — never expose secrets/stack traces.
    application.add_exception_handler(Exception, api_error_handler)
    application.add_exception_handler(APIError, api_domain_error_handler)  # type: ignore[arg-type]

    # Route registration.
    application.include_router(health.router)
    application.include_router(profile.router)
    application.include_router(filters.router)
    application.include_router(scheduler.router)
    application.include_router(jobs.router)
    application.include_router(matches.router)

    return application


# Module-level instance so ``uvicorn app.api.app:app`` works.
app = create_app()
