from __future__ import annotations

import logging
from dataclasses import dataclass

from dotenv import load_dotenv

from app.cli.commands import run_cli
from app.config.logging import configure_logging
from app.config.settings import Settings, get_settings

load_dotenv()


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    """Runtime application context assembled during startup."""

    settings: Settings


def create_application_context() -> ApplicationContext:
    """Create the application context without starting external integrations."""
    settings = get_settings()
    configure_logging(settings)
    logging.getLogger(__name__).info(
        "application_context_created",
        extra={"app_name": settings.app_name, "app_env": settings.app_env},
    )
    return ApplicationContext(settings=settings)


def main() -> None:
    """Run the StagePilot command-line application."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
