from __future__ import annotations

from collections.abc import Sequence

from app.config.settings import get_settings
from app.config.telegram_config import get_telegram_config
from app.domain.approval.errors import TelegramError
from app.infrastructure.telegram.messages import (
    format_daily_summary_message,
    format_linked_match_message,
)
from app.services.linkedin_mcp_pipeline_service import LinkedInMCPRecommendationResult


class TelegramNotificationService:
    """Sends pipeline notifications via Telegram.

    Contains NO approval logic. This is a thin notification adapter.
    """

    def __init__(self) -> None:
        self._config = get_telegram_config()
        self._settings = get_settings()

    def send_pipeline_summary(self, packages_queued: int, failed_count: int) -> None:
        """Send a pipeline summary notification to all allowed chats."""
        if not self._config.bot_token:
            msg = "Telegram bot token not configured"
            raise TelegramError(msg)

        text = self._build_summary_text(packages_queued, failed_count)
        self._broadcast(text)

    def _build_summary_text(self, packages_queued: int, failed_count: int) -> str:
        return format_daily_summary_message(queued=packages_queued, failed=failed_count)

    def send_queue_notification(self, queue_count: int) -> None:
        """Send a queue summary notification."""
        if not self._config.bot_token:
            msg = "Telegram bot token not configured"
            raise TelegramError(msg)

        text = format_daily_summary_message(queued=queue_count)
        self._broadcast(text)

    def send_linkedin_matches(
        self, recommendations: Sequence[LinkedInMCPRecommendationResult]
    ) -> int:
        """Send every above-threshold LinkedIn match to all allowed chats.

        Returns the number of messages broadcast (matches above the cutoff).
        """
        if not self._config.bot_token:
            msg = "Telegram bot token not configured"
            raise TelegramError(msg)

        above = [rec for rec in recommendations if rec.above_threshold]
        for rec in above:
            text = format_linked_match_message(
                title=rec.title,
                company=rec.company,
                location=rec.location,
                url=rec.url,
                final_score=rec.final_score,
                why=rec.explanation,
                matched_skills=list(rec.matched_skills),
                missing_skills=list(rec.missing_skills),
                max_length=self._config.max_message_length,
            )
            self._broadcast(text)
        return len(above)

    def _broadcast(self, text: str) -> None:
        """Send a message to all allowed chat IDs."""
        import asyncio
        from contextlib import suppress

        from telegram import Bot

        if not self._config.allowed_chat_ids:
            return

        async def _send() -> None:
            bot = Bot(token=self._config.bot_token)
            for chat_id in self._config.allowed_chat_ids:
                with suppress(Exception):
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

        try:
            asyncio.run(_send())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_send())
            finally:
                loop.close()
