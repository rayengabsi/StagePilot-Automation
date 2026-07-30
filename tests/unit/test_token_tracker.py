from __future__ import annotations

from unittest.mock import MagicMock

from app.domain.ai.enums import AIFeature
from app.services.token_tracker import TokenTracker


def test_track_creates_record() -> None:
    session = MagicMock()
    tracker = TokenTracker(session=session)
    usage = tracker.track(
        provider="gemini",
        model="gemini-2.0-flash-lite",
        feature=AIFeature.EXPLANATION,
        prompt_version="1.0.0",
        input_tokens=100,
        output_tokens=50,
        latency_ms=500,
    )
    assert usage.provider == "gemini"
    assert usage.model == "gemini-2.0-flash-lite"
    assert usage.feature == AIFeature.EXPLANATION
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.latency_ms == 500
    assert usage.prompt_version == "1.0.0"
    session.add.assert_called_once()
    session.flush.assert_called_once()


def test_track_estimates_cost() -> None:
    session = MagicMock()
    tracker = TokenTracker(session=session)
    usage = tracker.track(
        provider="gemini",
        model="gemini-2.0-flash-lite",
        feature=AIFeature.COVER_LETTER,
        prompt_version="1.0.0",
        input_tokens=1000,
        output_tokens=200,
        latency_ms=1000,
    )
    expected_cost = round((1000 / 1000.0) * 0.075, 6)
    assert usage.estimated_cost == expected_cost


def test_track_zero_tokens() -> None:
    session = MagicMock()
    tracker = TokenTracker(session=session)
    usage = tracker.track(
        provider="gemini",
        model="gemini-2.0-flash-lite",
        feature=AIFeature.RESUME_TAILORING,
        prompt_version="1.0.0",
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
    )
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0
    assert usage.estimated_cost == 0.0


def test_get_usage_returns_records() -> None:
    session = MagicMock()
    mock_query = MagicMock()
    mock_limited = MagicMock()
    mock_limited.all.return_value = []
    mock_query.limit.return_value = mock_limited
    session.query.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    tracker = TokenTracker(session=session)
    results = tracker.get_usage(limit=10)
    assert results == []


def test_get_usage_with_feature_filter() -> None:
    session = MagicMock()
    mock_query = MagicMock()
    mock_filtered = MagicMock()
    mock_limited = MagicMock()
    mock_limited.all.return_value = []
    mock_filtered.limit.return_value = mock_limited
    session.query.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.filter.return_value = mock_filtered
    tracker = TokenTracker(session=session)
    results = tracker.get_usage(limit=10, feature="explanation")
    mock_query.filter.assert_called_once()
    assert results == []


def test_cost_estimate_different_model() -> None:
    session = MagicMock()
    tracker = TokenTracker(session=session)
    cost = tracker._estimate_cost("unknown-model", 1000, 0)
    assert cost == 0.0
