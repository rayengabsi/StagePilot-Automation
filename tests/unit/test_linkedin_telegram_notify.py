"""Milestone 3: LinkedIn MCP matches are delivered to Telegram.

Covers the Telegram match card template and the notification adapter that
reuses the existing Telegram integration to send every above-threshold
LinkedIn recommendation.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from app.config.telegram_config import TelegramConfig
from app.domain.approval.errors import TelegramError
from app.infrastructure.telegram.messages import format_linked_match_message
from app.infrastructure.telegram.notification import TelegramNotificationService
from app.services.linkedin_mcp_pipeline_service import LinkedInMCPRecommendationResult


def _recommendation(
    *,
    title: str = "Software Engineer Intern (PFE)",
    company: str | None = "Acme Tech",
    location: str | None = "Tunis, Tunisia",
    url: str = "https://www.linkedin.com/jobs/view/mock-101",
    final_score: float = 41.0,
    explanation: str = "Matches your profile.",
    above_threshold: bool = True,
) -> LinkedInMCPRecommendationResult:
    return LinkedInMCPRecommendationResult(
        job_id=1,
        title=title,
        company=company,
        location=location,
        url=url,
        final_score=final_score,
        status="active",
        above_threshold=above_threshold,
        explanation=explanation,
        matched_skills=("Python", "Backend"),
        missing_skills=(),
    )


def test_format_linked_match_message_includes_all_fields() -> None:
    text = format_linked_match_message(
        title="Software Engineer Intern (PFE)",
        company="Acme Tech",
        location="Tunis, Tunisia",
        url="https://www.linkedin.com/jobs/view/mock-101",
        final_score=41.0,
        why="Matches your profile.",
        matched_skills=["Python", "Backend"],
        missing_skills=["Go"],
    )
    assert "New Career Match" in text
    assert "Company" in text and "Acme Tech" in text
    assert "Position" in text and "Software Engineer Intern (PFE)" in text
    assert "Location" in text and "Tunis, Tunisia" in text
    assert "Match" in text and "41%" in text
    assert "Why this matches" in text and "Matches your profile." in text
    assert "Apply" in text and "mock-101" in text
    assert "Python" in text and "Backend" in text
    assert "Go" in text


def test_format_linked_match_message_caps_skill_lists() -> None:
    text = format_linked_match_message(
        title="X",
        company="Y",
        location="Z",
        url="https://x",
        final_score=50.0,
        why="reason",
        matched_skills=[f"s{i}" for i in range(20)],
        missing_skills=[f"m{i}" for i in range(20)],
        max_matching_skills=3,
        max_missing_skills=2,
    )
    assert "s0" in text and "s2" in text
    assert "s3" not in text
    assert "m0" in text and "m1" in text
    assert "m2" not in text


def test_format_linked_match_message_defaults_missing_fields() -> None:
    text = format_linked_match_message(
        title="",
        company=None,
        location=None,
        url="",
        final_score=12.5,
        why="",
    )
    assert "Not specified" in text
    assert "12%" in text


def test_format_linked_match_message_respects_max_length() -> None:
    text = format_linked_match_message(
        title="Very long title " * 100,
        company="Acme Tech",
        location="Tunis",
        url="https://x",
        final_score=50.0,
        why="x",
        max_length=120,
    )
    assert len(text) <= 120
    assert text.endswith("...")


def test_send_linkedin_matches_broadcasts_above_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.infrastructure.telegram.notification.get_telegram_config",
        lambda: TelegramConfig(bot_token="test:token", allowed_chat_ids=[123]),
    )
    service = TelegramNotificationService()
    sent_texts: list[str] = []
    monkeypatch.setattr(
        service,
        "_broadcast",
        lambda text: sent_texts.append(text),
    )
    below = _recommendation(title="Below", final_score=10.0, above_threshold=False)

    sent = service.send_linkedin_matches((_recommendation(), below))

    assert sent == 1
    assert len(sent_texts) == 1
    assert "New Career Match" in sent_texts[0]


def test_send_linkedin_matches_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.telegram.notification.get_telegram_config",
        lambda: TelegramConfig(bot_token=""),
    )
    service = TelegramNotificationService()
    try:
        service.send_linkedin_matches((_recommendation(),))
    except TelegramError as exc:
        assert "token" in str(exc)
    else:
        raise AssertionError("expected TelegramError")


def test_send_linkedin_matches_respects_message_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.infrastructure.telegram.notification.get_telegram_config",
        lambda: TelegramConfig(
            bot_token="test:token",
            allowed_chat_ids=[123],
            max_message_length=80,
        ),
    )
    service = TelegramNotificationService()
    sent_texts: list[str] = []
    monkeypatch.setattr(service, "_broadcast", lambda text: sent_texts.append(text))

    service.send_linkedin_matches((_recommendation(),))

    assert len(sent_texts) == 1
    assert len(sent_texts[0]) <= 80


def test_send_linkedin_matches_empty_when_none_above_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.infrastructure.telegram.notification.get_telegram_config",
        lambda: TelegramConfig(bot_token="test:token", allowed_chat_ids=[123]),
    )
    service = TelegramNotificationService()
    broadcast = Mock()
    monkeypatch.setattr(service, "_broadcast", broadcast)

    sent = service.send_linkedin_matches((_recommendation(above_threshold=False),))

    assert sent == 0
    broadcast.assert_not_called()
