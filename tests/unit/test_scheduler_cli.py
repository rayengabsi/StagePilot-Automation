"""Tests for the `stagepilot scheduler` CLI commands.

The SchedulerService is mocked so no pipeline, database, or network is touched;
these tests cover command wiring, JSON output, and exit codes only.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.cli.commands import run_cli
from app.services.scheduler_service import SchedulerNotEnabledError


def _service_mock(outcome: dict[str, object] | None = None) -> MagicMock:
    svc = MagicMock()
    if outcome is not None:
        svc.run_once.return_value = outcome
    return svc


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_once_success_exits_zero(
    mock_cls: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_cls.return_value = _service_mock(
        {"status": "ok", "success": True, "result": {"fetched": 3}}
    )

    exit_code = run_cli(["scheduler", "once"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"status": "ok"' in out
    assert mock_cls.return_value.run_once.call_count == 1


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_once_no_jobs_is_a_valid_success(
    mock_cls: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_cls.return_value = _service_mock(
        {"status": "no_jobs", "success": True, "result": {"fetched": 0}}
    )

    exit_code = run_cli(["scheduler", "once"])

    assert exit_code == 0
    assert '"no_jobs"' in capsys.readouterr().out


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_once_failure_exits_one(
    mock_cls: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_cls.return_value = _service_mock(
        {
            "status": "error",
            "success": False,
            "result": {"status": "error", "message": "fetch failed"},
        }
    )

    exit_code = run_cli(["scheduler", "once"])

    assert exit_code == 1


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_once_auth_required_exits_two(
    mock_cls: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_cls.return_value = _service_mock(
        {
            "status": "auth_required",
            "success": False,
            "result": {"message": "LinkedIn session expired."},
        }
    )

    exit_code = run_cli(["scheduler", "once"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "session expired" in captured.err


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_status_prints_snapshot(
    mock_cls: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    svc = MagicMock()
    svc.status_snapshot.return_value = {
        "enabled": False,
        "running": False,
        "interval_minutes": 30,
        "last_run_status": None,
    }
    mock_cls.return_value = svc

    exit_code = run_cli(["scheduler", "status"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"enabled": false' in out
    assert '"interval_minutes": 30' in out


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_start_reports_disabled_configuration(
    mock_cls: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    svc = MagicMock()
    svc.start.side_effect = SchedulerNotEnabledError("Scheduler is disabled.")
    mock_cls.return_value = svc

    exit_code = run_cli(["scheduler", "start"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "disabled" in captured.err


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_start_passes_interval_override(mock_cls: MagicMock) -> None:
    svc = MagicMock()
    svc.start.return_value = 3
    mock_cls.return_value = svc

    exit_code = run_cli(["scheduler", "start", "--interval", "15"])

    assert exit_code == 0
    svc.start.assert_called_once_with(interval_minutes=15)


@patch("app.services.scheduler_service.SchedulerService")
def test_scheduler_stop_prints_outcome_and_exits_zero(
    mock_cls: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    svc = MagicMock()
    svc.request_stop.return_value = {
        "stopping": True,
        "running": True,
        "pid": 1234,
        "message": "Stop requested.",
    }
    mock_cls.return_value = svc

    exit_code = run_cli(["scheduler", "stop"])

    assert exit_code == 0
    assert '"stopping": true' in capsys.readouterr().out


@pytest.mark.parametrize("bad_interval", ["abc", "0", "-3"])
def test_scheduler_start_rejects_invalid_interval(bad_interval: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_cli(["scheduler", "start", "--interval", bad_interval])

    assert exc_info.value.code == 2
