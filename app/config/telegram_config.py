from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str = ""
    allowed_chat_ids: list[int] = field(default_factory=list)
    admin_users: list[int] = field(default_factory=list)
    max_message_length: int = 4096
    show_queue_position: bool = True
    show_score: bool = True
    show_skills: bool = True
    show_documents: bool = True
    delete_message_on_timeout: bool = True
    timeout_seconds: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelegramConfig:
        bot = data.get("bot", {})
        formatting = data.get("formatting", {})
        errors = data.get("errors", {})
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or bot.get("token", "")
        return cls(
            bot_token=token,
            allowed_chat_ids=bot.get("allowed_chat_ids", []),
            admin_users=bot.get("admin_users", []),
            max_message_length=formatting.get("max_message_length", 4096),
            show_queue_position=formatting.get("show_queue_position", True),
            show_score=formatting.get("show_score", True),
            show_skills=formatting.get("show_skills", True),
            show_documents=formatting.get("show_documents", True),
            delete_message_on_timeout=errors.get("delete_message_on_timeout", True),
            timeout_seconds=errors.get("timeout_seconds", 30),
        )

    @property
    def is_enabled(self) -> bool:
        return bool(self.bot_token)


@lru_cache
def get_telegram_config() -> TelegramConfig:
    """Load Telegram configuration.

    The bot token is a secret and is sourced from the ``TELEGRAM_BOT_TOKEN``
    environment variable (loaded from the gitignored ``.env``) rather than a
    committed TOML value. Chat IDs and formatting remain in ``config/telegram.toml``.
    """
    load_dotenv()
    config_path = Path("config/telegram.toml")
    if config_path.exists():
        raw = config_path.read_text(encoding="utf-8")
        data: dict[str, Any] = tomllib.loads(raw)
        return TelegramConfig.from_dict(data)
    return TelegramConfig()
