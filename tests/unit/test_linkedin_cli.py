"""Milestone 3: the ``stagepilot linkedin notify`` CLI command wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.cli.commands import _build_parser, _handle_linkedin_notify


def test_parser_exposes_linkedin_notify_command() -> None:
    parser = _build_parser()
    args = parser.parse_args(["linkedin", "notify", "--top", "5"])
    assert args.command == "linkedin"
    assert args.linkedin_command == "notify"
    assert hasattr(args, "handler")
    assert args.top == 5


@patch("app.services.linkedin_mcp_pipeline_service.LinkedInMCPPipelineService")
@patch("app.infrastructure.telegram.notification.TelegramNotificationService")
@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
def test_linkedin_notify_handler_runs_pipeline_and_sends(
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    mock_notifier: MagicMock,
    mock_service: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_factory.return_value.return_value = session

    result = MagicMock()
    result.source_id = 1
    result.fetched = 2
    result.matched_total = 1
    result.above_threshold = 1
    result.recommendations = []
    mock_service.return_value.run.return_value = result
    mock_notifier.return_value.send_linkedin_matches.return_value = 1

    args = MagicMock()
    args.top = None

    outcome = _handle_linkedin_notify(args, MagicMock())

    assert outcome == 0
    mock_service.return_value.run.assert_called_once_with(top_n=None)
    mock_notifier.return_value.send_linkedin_matches.assert_called_once_with([])
    captured = capsys.readouterr().out
    assert '"telegram_sent": 1' in captured


@patch("app.services.linkedin_mcp_pipeline_service.LinkedInMCPPipelineService")
@patch("app.infrastructure.telegram.notification.TelegramNotificationService")
@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
def test_linkedin_notify_handler_reports_zero_sent(
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    mock_notifier: MagicMock,
    mock_service: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_factory.return_value.return_value = session

    result = MagicMock()
    result.source_id = 9
    result.fetched = 0
    result.matched_total = 0
    result.above_threshold = 0
    result.recommendations = []
    mock_service.return_value.run.return_value = result
    mock_notifier.return_value.send_linkedin_matches.return_value = 0

    args = MagicMock()
    args.top = 10

    _handle_linkedin_notify(args, MagicMock())

    mock_service.return_value.run.assert_called_once_with(top_n=10)
    captured = capsys.readouterr().out
    assert '"telegram_sent": 0' in captured
