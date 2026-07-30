from __future__ import annotations

from app.config.settings import get_settings
from app.config.telegram_config import get_telegram_config
from app.domain.approval.errors import TelegramError


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
        lines: list[str] = []
        lines.append("StagePilot Pipeline Complete")
        lines.append("")

        if packages_queued > 0:
            lines.append(
                f"{packages_queued} new internship opportunities found and queued for review."
            )
            lines.append("")
            lines.append("Use /queue to review them.")
        else:
            lines.append("No new opportunities found this run.")

        if failed_count > 0:
            lines.append("")
            lines.append(f"Warning: {failed_count} job(s) encountered errors.")

        return "\n".join(lines)

    def send_queue_notification(self, queue_count: int) -> None:
        """Send a queue summary notification."""
        if not self._config.bot_token:
            msg = "Telegram bot token not configured"
            raise TelegramError(msg)

        text = (
            f"Approval Queue Status\n"
            f"Current queue size: {queue_count}\n"
            f"Use /queue to review pending applications."
        )
        self._broadcast(text)

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
                    await bot.send_message(chat_id=chat_id, text=text)

        try:
            asyncio.run(_send())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_send())
            finally:
                loop.close()
