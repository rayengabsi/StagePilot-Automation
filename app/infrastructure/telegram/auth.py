from __future__ import annotations

from app.config.telegram_config import TelegramConfig
from app.domain.approval.errors import UnauthorizedError


class TelegramAuth:
    """Validates Telegram user authorization."""

    def __init__(self, config: TelegramConfig) -> None:
        self._config = config

    def authorize(self, user_id: int) -> None:
        if not self._config.allowed_chat_ids:
            return
        if user_id not in self._config.allowed_chat_ids and user_id not in self._config.admin_users:
            msg = f"User {user_id} is not authorized"
            raise UnauthorizedError(msg)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self._config.admin_users
