from __future__ import annotations

import pytest
from app.config.telegram_config import TelegramConfig
from app.domain.approval.errors import UnauthorizedError
from app.infrastructure.telegram.auth import TelegramAuth


@pytest.fixture
def auth_with_allowed() -> TelegramAuth:
    config = TelegramConfig(
        bot_token="test:token",
        allowed_chat_ids=[123, 456],
        admin_users=[456],
    )
    return TelegramAuth(config)


@pytest.fixture
def auth_no_restrictions() -> TelegramAuth:
    config = TelegramConfig(bot_token="test:token", allowed_chat_ids=[], admin_users=[])
    return TelegramAuth(config)


def test_authorize_allowed_user(auth_with_allowed: TelegramAuth) -> None:
    auth_with_allowed.authorize(123)
    auth_with_allowed.authorize(456)


def test_authorize_unauthorized_user(auth_with_allowed: TelegramAuth) -> None:
    with pytest.raises(UnauthorizedError):
        auth_with_allowed.authorize(999)


def test_authorize_no_restrictions(auth_no_restrictions: TelegramAuth) -> None:
    auth_no_restrictions.authorize(0)
    auth_no_restrictions.authorize(999999)


def test_is_admin(auth_with_allowed: TelegramAuth) -> None:
    assert auth_with_allowed.is_admin(456) is True
    assert auth_with_allowed.is_admin(123) is False
    assert auth_with_allowed.is_admin(999) is False
