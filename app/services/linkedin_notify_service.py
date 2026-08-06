"""End-to-end LinkedIn MCP → matching → Telegram delivery service.

This service is the single entry point behind ``stagepilot linkedin notify``.
It:

1. starts LinkedIn MCP (via the connector),
2. runs the existing matching pipeline (search → normalize → score → explain),
3. filters to the matches above the configured threshold that have *not* yet
   been delivered to Telegram,
4. sends them through the existing Telegram notification service, and
5. records them as notified so the same job is never pushed twice.

It never crashes the pipeline: expired sessions and MCP/Telegram failures are
reported on the returned result instead of raising.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config.linkedin_mcp_config import get_linkedin_mcp_config
from app.config.settings import Settings, get_settings
from app.domain.jobs.errors import LinkedInSessionExpiredError
from app.infrastructure.linkedin_mcp.notification_state import (
    JsonNotificationStateRepository,
    NotificationStateRepository,
)
from app.infrastructure.telegram.notification import TelegramNotificationService
from app.services.linkedin_mcp_pipeline_service import (
    LinkedInMCPPipelineResult,
    LinkedInMCPPipelineService,
)

logger = logging.getLogger(__name__)

_AUTH_MESSAGE = (
    "LinkedIn session expired.\n"
    "\n"
    "Please login once by running:\n"
    "\n"
    "python -m linkedin_mcp_server --login\n"
    "\n"
    "After login StagePilot will automatically use your saved session."
)


@dataclass(frozen=True, slots=True)
class LinkedInNotifyResult:
    """Outcome of one LinkedIn notify run."""

    status: str
    source_id: int | None = None
    fetched: int = 0
    duplicates: int = 0
    rejected: int = 0
    matched_total: int = 0
    above_threshold: int = 0
    already_notified: int = 0
    new_matches: int = 0
    telegram_sent: int = 0
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "status": self.status,
            "source_id": self.source_id,
            "fetched": self.fetched,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "matched_total": self.matched_total,
            "above_threshold": self.above_threshold,
            "already_notified": self.already_notified,
            "new_matches": self.new_matches,
            "telegram_sent": self.telegram_sent,
            "message": self.message,
        }


class LinkedInNotifyService:
    """Run LinkedIn discovery, matching, dedup, and Telegram delivery."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        state_repo: NotificationStateRepository | None = None,
        notifier: TelegramNotificationService | None = None,
        pipeline: LinkedInMCPPipelineService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._state = state_repo or JsonNotificationStateRepository(
            get_linkedin_mcp_config().state_file
        )
        self._notifier = notifier or TelegramNotificationService()
        self._pipeline = pipeline or LinkedInMCPPipelineService(
            session=self._session, settings=self._settings
        )

    def run(self, top_n: int | None = None) -> LinkedInNotifyResult:
        """Run the full lifecycle and return a never-raising result."""
        logger.info("LinkedIn MCP started")
        try:
            pipeline_result = self._pipeline.run(top_n=top_n)
        except LinkedInSessionExpiredError:
            logger.warning("LinkedIn session expired; login required")
            return LinkedInNotifyResult(status="auth_required", message=_AUTH_MESSAGE)
        except Exception as exc:
            logger.error("LinkedIn notify pipeline failed: %s", exc)
            return LinkedInNotifyResult(status="error", message=str(exc))

        return self._deliver(pipeline_result)

    def _deliver(self, pipeline_result: LinkedInMCPPipelineResult) -> LinkedInNotifyResult:
        above = [rec for rec in pipeline_result.recommendations if rec.above_threshold]
        new_matches = [rec for rec in above if not self._is_notified(rec.url)]
        already = len(above) - len(new_matches)

        telegram_sent = 0
        if new_matches:
            telegram_sent = self._notifier.send_linkedin_matches(new_matches)
            for rec in new_matches:
                self._mark_notified(rec.url)

        logger.info(
            "LinkedIn notify: found=%d matched=%d above=%d new=%d already=%d sent=%d",
            pipeline_result.fetched,
            pipeline_result.matched_total,
            len(above),
            len(new_matches),
            already,
            telegram_sent,
        )

        return LinkedInNotifyResult(
            status="ok",
            source_id=pipeline_result.source_id,
            fetched=pipeline_result.fetched,
            duplicates=pipeline_result.duplicates,
            rejected=pipeline_result.rejected,
            matched_total=pipeline_result.matched_total,
            above_threshold=len(above),
            already_notified=already,
            new_matches=len(new_matches),
            telegram_sent=telegram_sent,
            message="LinkedIn MCP closed",
        )

    def _is_notified(self, url: str) -> bool:
        return self._state.is_notified(url)

    def _mark_notified(self, url: str) -> None:
        self._state.mark_notified(url)
