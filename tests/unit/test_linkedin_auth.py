"""Unit tests for the LinkedIn session provider over the real server's CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.config.linkedin_mcp_config import LinkedInMCPConfig
from app.infrastructure.linkedin_mcp.auth import (
    LinkedInAuthError,
    LinkedInMCPAuthClient,
    LinkedInSessionStatus,
)


def _config(**overrides: object) -> LinkedInMCPConfig:
    fields: dict[str, object] = {
        "command": "python",
        "cwd": ".",
        "module": "linkedin_mcp_server",
        "transport": "stdio",
        "timeout_seconds": 90.0,
        "tool_timeout_seconds": 180.0,
        "log_level": "WARNING",
        "max_jobs": 8,
        "max_pages": 3,
        "date_posted": "",
        "sort_by": "",
        "job_type": "",
        "experience_level": "",
        "expired_markers": ("login required",),
        "user_data_dir": "",
        "login_headed": True,
        "login_timeout_seconds": 3600.0,
        "status_timeout_seconds": 300.0,
        "status_probe_timeout_seconds": 20.0,
        "startup_timeout_seconds": 90.0,
        "shutdown_timeout_seconds": 15.0,
        "ready_poll_seconds": 2.0,
        "state_file": Path("data/linkedin/notified.json"),
        "max_matching_skills": 5,
        "max_missing_skills": 5,
        "retry_attempts": 3,
        "retry_delay_seconds": 2.0,
        "retry_backoff": 2.0,
    }
    fields.update(overrides)
    return LinkedInMCPConfig(**fields)


def test_command_builds_status_args() -> None:
    client = LinkedInMCPAuthClient(_config(user_data_dir="profile", log_level="DEBUG"))
    args = client._command("--status")
    assert args[:4] == ["python", "-m", "linkedin_mcp_server", "--status"]
    assert "--log-level" in args and "DEBUG" in args
    assert "--user-data-dir" in args and "profile" in args


def test_command_omits_user_data_dir_when_empty() -> None:
    client = LinkedInMCPAuthClient(_config())
    assert "--user-data-dir" not in client._command("--status")


def test_is_authenticated_true_on_zero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    result = MagicMock(returncode=0)
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=result))
    client = LinkedInMCPAuthClient(_config())

    assert client.is_authenticated() is True
    status_args = subprocess.run.call_args[0][0]
    assert "--status" in status_args


def test_is_authenticated_false_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=MagicMock(returncode=1)))
    client = LinkedInMCPAuthClient(_config())

    assert client.is_authenticated() is False


def test_login_uses_headed_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=MagicMock(returncode=0)))
    client = LinkedInMCPAuthClient(_config(login_headed=True))

    assert client.login() is True
    login_args = subprocess.run.call_args[0][0]
    assert "--login" in login_args
    assert "--no-headless" in login_args


def test_login_respects_headless_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=MagicMock(returncode=0)))
    client = LinkedInMCPAuthClient(_config(login_headed=False))

    client.login()
    assert "--no-headless" not in subprocess.run.call_args[0][0]


def test_login_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=MagicMock(returncode=1)))
    client = LinkedInMCPAuthClient(_config())

    assert client.login() is False


def test_status_raises_on_missing_command(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> MagicMock:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", _raise)
    client = LinkedInMCPAuthClient(_config())

    with pytest.raises(LinkedInAuthError, match="command not found"):
        client.is_authenticated()


def test_status_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> MagicMock:
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=5)

    monkeypatch.setattr(subprocess, "run", _raise)
    client = LinkedInMCPAuthClient(_config(status_timeout_seconds=5))

    with pytest.raises(LinkedInAuthError, match="timed out"):
        client.is_authenticated()


def test_session_status_authenticated_on_zero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=MagicMock(returncode=0)))
    client = LinkedInMCPAuthClient(_config())

    assert client.session_status() is LinkedInSessionStatus.AUTHENTICATED
    status_args = subprocess.run.call_args[0][0]
    assert "--status" in status_args


def test_session_status_needs_login_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=MagicMock(returncode=1)))
    client = LinkedInMCPAuthClient(_config())

    assert client.session_status() is LinkedInSessionStatus.NEEDS_LOGIN


def test_session_status_timeout_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> MagicMock:
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=3)

    monkeypatch.setattr(subprocess, "run", _raise)
    client = LinkedInMCPAuthClient(_config())

    assert client.session_status(timeout=3.0) is LinkedInSessionStatus.TIMEOUT


def test_session_status_error_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: object, **_kwargs: object) -> MagicMock:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", _raise)
    client = LinkedInMCPAuthClient(_config())

    assert client.session_status() is LinkedInSessionStatus.ERROR
