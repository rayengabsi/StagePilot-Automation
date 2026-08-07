"""Tests for the Telegram notification adapter, including network-free broadcast paths."""

from __future__ import annotations

import asyncio

import pytest
from app.config.telegram_config import TelegramConfig
from app.domain.approval.errors import TelegramError
from app.infrastructure.telegram.notification import TelegramNotificationService


def _service(
    monkeypatch: pytest.MonkeyPatch, config: TelegramConfig
) -> TelegramNotificationService:
    monkeypatch.setattr(
        "app.infrastructure.telegram.notification.get_telegram_config", lambda: config
    )
    monkeypatch.setattr("app.infrastructure.telegram.notification.get_settings", lambda: object())
    return TelegramNotificationService()


def test_pipeline_summary_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(monkeypatch, TelegramConfig(bot_token=""))
    try:
        service.send_pipeline_summary(packages_queued=1, failed_count=0)
    except TelegramError as exc:
        assert "token" in str(exc)
    else:
        raise AssertionError("expected TelegramError")


def test_queue_notification_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(monkeypatch, TelegramConfig(bot_token=""))
    try:
        service.send_queue_notification(queue_count=2)
    except TelegramError as exc:
        assert "token" in str(exc)
    else:
        raise AssertionError("expected TelegramError")


def test_pipeline_summary_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(monkeypatch, TelegramConfig(bot_token="t"))
    sent: list[str] = []
    monkeypatch.setattr(service, "_broadcast", sent.append)
    service.send_pipeline_summary(packages_queued=3, failed_count=1)
    assert len(sent) == 1
    assert "StagePilot" in sent[0]


def test_queue_notification_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(monkeypatch, TelegramConfig(bot_token="t"))
    sent: list[str] = []
    monkeypatch.setattr(service, "_broadcast", sent.append)
    service.send_queue_notification(queue_count=4)
    assert len(sent) == 1


def test_broadcast_noop_when_no_chat_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(monkeypatch, TelegramConfig(bot_token="t", allowed_chat_ids=[]))
    service._broadcast("hello")


def test_broadcast_sends_to_all_chat_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[int, str]] = []

    class FakeBot:
        def __init__(self, token: str) -> None:
            self.token = token

        async def send_message(self, chat_id: int, text: str, parse_mode: str) -> None:
            sent.append((chat_id, text))

    monkeypatch.setattr("telegram.Bot", FakeBot)
    service = _service(monkeypatch, TelegramConfig(bot_token="t", allowed_chat_ids=[1, 2]))
    service._broadcast("message")
    assert sent == [(1, "message"), (2, "message")]


def test_broadcast_falls_back_when_loop_running(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[int, str]] = []

    class FakeBot:
        def __init__(self, token: str) -> None:
            self.token = token

        async def send_message(self, chat_id: int, text: str, parse_mode: str) -> None:
            sent.append((chat_id, text))

    monkeypatch.setattr("telegram.Bot", FakeBot)

    def _raise_runtime_error(coro: object) -> None:
        if asyncio.iscoroutine(coro):
            coro.close()
        raise RuntimeError()

    monkeypatch.setattr("asyncio.run", _raise_runtime_error)
    service = _service(monkeypatch, TelegramConfig(bot_token="t", allowed_chat_ids=[7]))
    service._broadcast("fallback")
    assert sent == [(7, "fallback")]
