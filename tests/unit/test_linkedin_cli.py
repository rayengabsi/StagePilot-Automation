"""Milestone 3: the ``stagepilot linkedin notify`` CLI command wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.cli.commands import (
    _build_parser,
    _handle_linkedin_login,
    _handle_linkedin_notify,
    _handle_linkedin_status,
)
from app.infrastructure.linkedin_mcp.auth import LinkedInSessionStatus
from app.services.linkedin_notify_service import LinkedInNotifyResult


def test_parser_exposes_linkedin_commands() -> None:
    parser = _build_parser()
    notify = parser.parse_args(["linkedin", "notify", "--top", "5"])
    assert notify.command == "linkedin"
    assert notify.linkedin_command == "notify"
    assert hasattr(notify, "handler")
    assert notify.top == 5

    status = parser.parse_args(["linkedin", "status"])
    assert status.linkedin_command == "status"

    login = parser.parse_args(["linkedin", "login"])
    assert login.linkedin_command == "login"


def _notify_result(**overrides: object) -> LinkedInNotifyResult:
    fields = {
        "status": "ok",
        "source_id": 1,
        "fetched": 2,
        "duplicates": 0,
        "rejected": 0,
        "matched_total": 1,
        "above_threshold": 1,
        "already_notified": 0,
        "new_matches": 1,
        "telegram_sent": 1,
        "message": None,
    }
    fields.update(overrides)
    return LinkedInNotifyResult(**fields)


@patch("app.infrastructure.linkedin_mcp.auth.LinkedInMCPAuthClient")
@patch("app.services.linkedin_notify_service.LinkedInNotifyService")
@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
def test_linkedin_notify_handler_runs_pipeline_and_sends(
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    mock_service: MagicMock,
    mock_auth: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_factory.return_value.return_value = session
    mock_service.return_value.run.return_value = _notify_result()
    mock_auth.return_value.session_status.return_value = LinkedInSessionStatus.AUTHENTICATED

    args = MagicMock()
    args.top = None
    args.no_login = False

    outcome = _handle_linkedin_notify(args, MagicMock())

    assert outcome == 0
    mock_service.return_value.run.assert_called_once_with(top_n=None)
    captured = capsys.readouterr().out
    assert '"telegram_sent": 1' in captured


@patch("app.infrastructure.linkedin_mcp.auth.LinkedInMCPAuthClient")
@patch("app.services.linkedin_notify_service.LinkedInNotifyService")
@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
def test_linkedin_notify_handler_reports_zero_sent(
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    mock_service: MagicMock,
    mock_auth: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_factory.return_value.return_value = session
    mock_service.return_value.run.return_value = _notify_result(
        status="ok", telegram_sent=0, above_threshold=0, new_matches=0
    )
    mock_auth.return_value.session_status.return_value = LinkedInSessionStatus.AUTHENTICATED

    args = MagicMock()
    args.top = 10
    args.no_login = False

    _handle_linkedin_notify(args, MagicMock())

    mock_service.return_value.run.assert_called_once_with(top_n=10)
    captured = capsys.readouterr().out
    assert '"telegram_sent": 0' in captured


@patch("app.infrastructure.linkedin_mcp.auth.LinkedInMCPAuthClient")
@patch("app.services.linkedin_notify_service.LinkedInNotifyService")
@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
def test_linkedin_notify_fails_fast_with_no_login_when_unauthenticated(
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    mock_service: MagicMock,
    mock_auth: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_factory.return_value.return_value = session
    mock_auth.return_value.session_status.return_value = LinkedInSessionStatus.NEEDS_LOGIN

    args = MagicMock()
    args.top = None
    args.no_login = True

    outcome = _handle_linkedin_notify(args, MagicMock())

    assert outcome == 2
    mock_service.return_value.run.assert_not_called()
    mock_auth.return_value.login.assert_not_called()
    assert "linkedin login" in capsys.readouterr().err


@patch("app.infrastructure.linkedin_mcp.auth.LinkedInMCPAuthClient")
@patch("app.services.linkedin_notify_service.LinkedInNotifyService")
@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
def test_linkedin_notify_runs_login_when_unauthenticated(
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    mock_service: MagicMock,
    mock_auth: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_factory.return_value.return_value = session
    mock_service.return_value.run.return_value = _notify_result()
    mock_auth.return_value.session_status.return_value = LinkedInSessionStatus.NEEDS_LOGIN
    mock_auth.return_value.login.return_value = True

    args = MagicMock()
    args.top = None
    args.no_login = False

    outcome = _handle_linkedin_notify(args, MagicMock())

    assert outcome == 0
    mock_auth.return_value.login.assert_called_once()
    mock_service.return_value.run.assert_called_once_with(top_n=None)


@patch("app.infrastructure.linkedin_mcp.auth.LinkedInMCPAuthClient")
def test_linkedin_status_returns_exit_codes(mock_auth: MagicMock) -> None:
    mock_auth.return_value.session_status.return_value = LinkedInSessionStatus.AUTHENTICATED
    assert _handle_linkedin_status(MagicMock(), MagicMock()) == 0

    mock_auth.return_value.session_status.return_value = LinkedInSessionStatus.NEEDS_LOGIN
    assert _handle_linkedin_status(MagicMock(), MagicMock()) == 2


@patch("app.infrastructure.linkedin_mcp.auth.LinkedInMCPAuthClient")
def test_linkedin_login_runs_and_persists(mock_auth: MagicMock) -> None:
    mock_auth.return_value.login.return_value = True
    assert _handle_linkedin_login(MagicMock(), MagicMock()) == 0
    mock_auth.return_value.login.assert_called_once()

    mock_auth.return_value.login.return_value = False
    assert _handle_linkedin_login(MagicMock(), MagicMock()) == 2
