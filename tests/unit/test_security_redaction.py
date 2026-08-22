"""Tests for sensitive-data redaction in scheduler error reporting."""

from __future__ import annotations

from app.services.scheduler_service import _sanitize_error


class _FakeError(Exception):
    """Minimal exception for testing sanitization."""


def test_telegram_style_token_is_redacted() -> None:
    """A Telegram-format token must not appear in sanitized output."""
    fake_token = "123456789:ABCDefGhIjKlMnOpQrStUvWxYz01234567"  # noqa: S105
    exc = _FakeError(f"Request failed: {fake_token}")
    result = _sanitize_error(exc)
    assert fake_token not in result
    assert "[REDACTED]" in result


def test_generic_long_secret_is_redacted() -> None:
    """A long alphanumeric secret string must not appear in sanitized output."""
    fake_secret = "sk_abcdefghijklmnopqrstuvwxyz1234567890"  # noqa: S105
    exc = _FakeError(f"Auth failed: {fake_secret}")
    result = _sanitize_error(exc)
    assert fake_secret not in result
    assert "[REDACTED]" in result


def test_normal_error_message_passes_through() -> None:
    """Normal error messages without secrets must not be altered."""
    exc = _FakeError("Connection refused")
    result = _sanitize_error(exc)
    assert result == "Connection refused"


def test_empty_message_passes_through() -> None:
    """An empty exception message must not crash."""
    exc = _FakeError("")
    result = _sanitize_error(exc)
    assert result == ""


def test_short_token_is_not_redacted() -> None:
    """Short strings must NOT be treated as secrets (avoid false positives)."""
    exc = _FakeError("Error code 42")
    result = _sanitize_error(exc)
    assert result == "Error code 42"


def test_test_telegram_secret_value_is_redacted() -> None:
    """A Telegram token containing special chars must be redacted."""
    fake_token = "1234567890:AA/test_token_value_here_for_regression"  # noqa: S105
    exc = _FakeError(f"Bot error: {fake_token}")
    result = _sanitize_error(exc)
    assert fake_token not in result
