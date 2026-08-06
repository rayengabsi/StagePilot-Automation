"""Unit tests for the stagepilot doctor diagnostics.

All probes are stubbed so no real database, network, or LinkedIn browser is
touched; the point is to verify the diag run is isolated and reports honestly.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import NoReturn

import pytest
from app.infrastructure.diagnostics.doctor import DoctorCheck, run_doctor


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def execute(self, statement: object) -> None:
        self.executed.append(str(statement))


class _FakeAuth:
    def __init__(self, _config: object, *, authenticated: bool = True) -> None:
        self._authenticated = authenticated

    def is_authenticated(self) -> bool:
        return self._authenticated


def _stub_linkedin(monkeypatch: pytest.MonkeyPatch, *, command: str = "x.exe") -> None:
    monkeypatch.setattr(
        "app.infrastructure.diagnostics.doctor.get_linkedin_mcp_config",
        lambda: SimpleNamespace(command=command, module="linkedin_mcp_server"),
    )
    monkeypatch.setattr(
        "app.infrastructure.diagnostics.doctor._command_exists",
        lambda _c: bool(command),
    )
    monkeypatch.setattr(
        "app.infrastructure.diagnostics.doctor._session_cookie_present",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.infrastructure.diagnostics.doctor.LinkedInMCPAuthClient",
        _FakeAuth,
    )


def test_run_doctor_returns_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_linkedin(monkeypatch)
    monkeypatch.setattr(
        "app.infrastructure.diagnostics.doctor.get_telegram_config",
        lambda: SimpleNamespace(bot_token="bot", allowed_chat_ids=[1, 2]),
    )

    report = run_doctor(session_factory=lambda: _FakeSession())

    assert report.all_ok is True
    assert report.python
    assert report.platform
    names = [check.name for check in report.checks]
    assert {"database", "telegram", "linkedin_session", "mcp_server"} <= set(names)
    assert all(isinstance(check, DoctorCheck) for check in report.checks)


def test_run_doctor_telegram_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_linkedin(monkeypatch)
    monkeypatch.setattr(
        "app.infrastructure.diagnostics.doctor.get_telegram_config",
        lambda: SimpleNamespace(bot_token="", allowed_chat_ids=[]),
    )
    report = run_doctor(session_factory=lambda: _FakeSession())
    telegram = next(c for c in report.checks if c.name == "telegram")
    assert telegram.ok is False
    assert "token" in telegram.message


def test_linkedin_session_flags_missing_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_linkedin(monkeypatch)
    monkeypatch.setattr(
        "app.infrastructure.diagnostics.doctor._session_cookie_present",
        lambda: False,
    )
    report = run_doctor(session_factory=lambda: _FakeSession())
    linkedin = next(c for c in report.checks if c.name == "linkedin_session")
    assert linkedin.ok is False
    assert "login" in linkedin.message


def test_run_doctor_survives_blown_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_sf):  # noqa: ANN001, ANN202
        raise RuntimeError("kaboom")

    monkeypatch.setattr("app.infrastructure.diagnostics.doctor._probe_python_version", _boom)
    _stub_linkedin(monkeypatch)

    report = run_doctor(session_factory=lambda: _FakeSession())

    python = next(c for c in report.checks if c.name == "_boom")
    assert python.ok is False
    assert "kaboom" in python.message
    assert any(c.name == "dependencies" for c in report.checks)


def test_database_probe_reports_failure_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_linkedin(monkeypatch)

    def _bad_sf() -> NoReturn:
        raise RuntimeError("refused")

    report = run_doctor(session_factory=_bad_sf)
    db = next(c for c in report.checks if c.name == "database")
    assert db.ok is False
    assert "refused" in db.message


def test_database_probe_without_session_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_linkedin(monkeypatch)
    report = run_doctor(session_factory=None)
    db = next(c for c in report.checks if c.name == "database")
    assert db.ok is False
    assert "no session factory" in db.message


def test_report_to_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_linkedin(monkeypatch)
    report = run_doctor(session_factory=lambda: _FakeSession())
    data = report.to_dict()
    assert "python" in data and "checks" in data
    assert isinstance(data["all_ok"], bool)


def test_doctor_subcommand_is_wired() -> None:
    from app.cli.commands import _build_parser

    args = _build_parser().parse_args(["doctor", "--json"])
    assert args.command == "doctor"
    assert args.json is True
    assert callable(args.handler)
