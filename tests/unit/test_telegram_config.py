"""Tests for Telegram configuration secret sourcing.

The bot token must come from the environment (never a committed TOML value)
so that no credential lives in the repository.
"""

from __future__ import annotations

import pytest
from app.config.telegram_config import TelegramConfig


def test_from_dict_prefers_environment_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    config = TelegramConfig.from_dict({"bot": {"token": "committed-token"}})

    value = config.bot_token
    assert value == "env-token"
    assert config.is_enabled is True


def test_from_dict_falls_back_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    config = TelegramConfig.from_dict({"bot": {"token": "committed-token"}})

    value = config.bot_token
    assert value == "committed-token"
    assert config.is_enabled is True


def test_from_dict_empty_token_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    config = TelegramConfig.from_dict({"bot": {"token": ""}})

    assert config.bot_token == ""
    assert config.is_enabled is False


def test_is_enabled_follows_token() -> None:
    assert TelegramConfig(bot_token="").is_enabled is False
    assert TelegramConfig(bot_token="x").is_enabled is True
