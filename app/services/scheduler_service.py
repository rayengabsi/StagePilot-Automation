from __future__ import annotations

import logging
import time
from enum import StrEnum

from app.config.settings import Settings, get_settings
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.services.pipeline_orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class ScheduleInterval(StrEnum):
    HOURLY = "hourly"
    EVERY_6_HOURS = "every_6_hours"
    DAILY = "daily"


class SchedulerService:
    """Invokes PipelineOrchestrator on a configurable schedule."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def run_once(self) -> dict:
        """Run the pipeline once and return the result."""
        engine = create_database_engine(self._settings)
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            orchestrator = PipelineOrchestrator(session=session, settings=self._settings)
            result = orchestrator.run()
        return {
            "packages_created": result.packages_created,
            "queued": result.queued,
            "jobs_found": result.jobs_found,
            "matched": result.matched,
            "duration_seconds": result.duration_seconds,
            "telegram_sent": result.telegram_sent,
        }

    def start(self, interval: ScheduleInterval) -> None:
        """Start the scheduler loop (blocking)."""
        interval_seconds = self._interval_to_seconds(interval)
        logger.info(
            "Scheduler started with interval %s (%d seconds)",
            interval,
            interval_seconds,
        )

        while True:
            try:
                logger.info("Scheduler: starting pipeline run...")
                result = self.run_once()
                logger.info(
                    "Scheduler: pipeline complete — %d packages queued in %.1fs",
                    result["queued"],
                    result["duration_seconds"],
                )
            except Exception as exc:
                logger.exception("Scheduler: pipeline failed — %s", exc)

            time.sleep(interval_seconds)

    @staticmethod
    def _interval_to_seconds(interval: ScheduleInterval) -> int:
        if interval == ScheduleInterval.HOURLY:
            return 3600
        if interval == ScheduleInterval.EVERY_6_HOURS:
            return 21600
        if interval == ScheduleInterval.DAILY:
            return 86400
        return 3600
