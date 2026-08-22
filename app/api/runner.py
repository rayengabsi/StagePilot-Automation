"""Convenience CLI entry point for running the StagePilot API.

Usage::

    uv run stagepilot api
    uv run stagepilot api --port 9000 --reload
"""

from __future__ import annotations

import uvicorn

from app.config.settings import get_settings


def run_api(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the FastAPI server."""
    settings = get_settings()
    log_level = settings.log_level.lower() if settings.log_level else "info"
    uvicorn.run(
        "app.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )
