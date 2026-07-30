from __future__ import annotations

from telegram import Update
from telegram.ext import ApplicationBuilder

from app.config.settings import Settings
from app.config.telegram_config import get_telegram_config
from app.domain.approval.errors import TelegramError
from app.infrastructure.telegram.handlers import build_handlers


def run_telegram_bot(_settings: Settings) -> None:
    """Run the Telegram bot (blocking)."""
    telegram_config = get_telegram_config()

    if not telegram_config.bot_token:
        msg = "Telegram bot token not configured. Set bot_token in config/telegram.toml"
        raise TelegramError(msg)

    application = ApplicationBuilder().token(telegram_config.bot_token).build()

    for handler in build_handlers():
        application.add_handler(handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)
