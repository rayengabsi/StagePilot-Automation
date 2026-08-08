"""Unit tests for the LinkedIn session provider over the real server.

Auth status reads the server's persisted session files; login drives the
server's ``--login`` one-shot with output redirected to files (never a pipe).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from app.config.linkedin_mcp_config import LinkedInMCPConfig
from app.infrastructure.linkedin_mcp import auth as auth_module
from app.infrastructure.linkedin_mcp.auth import (
    LinkedInAuthError,
    LinkedInMCPAuthClient,
    LinkedInSessionStatus,
    ServerProcessResult,
    _session_files,
    _spawn_server,
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


def _ok(
    returncode: int | None = 0, *, timed_out: bool = False, pid: int | None = 7
) -> ServerProcessResult:
    return ServerProcessResult(
        launched=True,
        returncode=returncode,
        timed_out=timed_out,
        pid=pid,
        stdout="",
        stderr="",
    )


def _stub_spawn(monkeypatch: pytest.MonkeyPatch, result: ServerProcessResult) -> dict[str, object]:
    captured: dict[str, object] = {}

    def _spawn(args: list[str], *, cwd: str, timeout: float, mode: str) -> ServerProcessResult:
        captured["args"] = args
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        captured["mode"] = mode
        return result

    monkeypatch.setattr(auth_module, "_spawn_server", _spawn)
    return captured


def _build_session_tree(base: Path, *, valid: bool = True) -> Path:
    """Create a server-style auth layout and return the profile directory."""
    auth_root = base / "auth"
    profile = auth_root / "profile"
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    (profile / "Default" / "Preferences").write_text("{}", encoding="utf-8")
    (auth_root / "cookies.json").write_text(
        json.dumps([{"name": "li_at", "value": "AQED-secret"}]), encoding="utf-8"
    )
    if valid:
        state = {"login_generation": "g-1", "source_runtime_id": "win-x86_64-host"}
    else:
        state = "not-a-dict"
    (auth_root / "source-state.json").write_text(
        json.dumps(state) if isinstance(state, dict) else state,
        encoding="utf-8",
    )
    return profile


def test_command_builds_login_args() -> None:
    client = LinkedInMCPAuthClient(_config(user_data_dir="profile", log_level="DEBUG"))
    args = client._command("--login")
    assert args[:4] == ["python", "-m", "linkedin_mcp_server", "--login"]
    assert "--log-level" in args and "DEBUG" in args
    assert "--user-data-dir" in args and "profile" in args


def test_command_omits_user_data_dir_when_empty() -> None:
    client = LinkedInMCPAuthClient(_config())
    assert "--user-data-dir" not in client._command("--login")


def test_base_arguments_include_configured_user_data_dir() -> None:
    cfg = _config(user_data_dir="~/.linkedin-mcp/profile-active")
    args = cfg.base_arguments()
    assert "--user-data-dir" in args
    assert any("profile-active" in arg for arg in args)


def test_base_arguments_omit_user_data_dir_when_empty() -> None:
    args = _config().base_arguments()
    assert "--user-data-dir" not in args


def test_session_files_default_and_custom_paths(tmp_path: Path) -> None:
    profile, cookies, source_state = _session_files(_config())
    assert profile.name == "profile"
    assert cookies.parent == profile.parent
    assert source_state.name == "source-state.json"

    custom, _, _ = _session_files(_config(user_data_dir=str(tmp_path / "eng-profile")))
    assert custom == tmp_path / "eng-profile"


def test_is_authenticated_true_when_all_artifacts_present(tmp_path: Path) -> None:
    profile = _build_session_tree(tmp_path)
    client = LinkedInMCPAuthClient(_config(user_data_dir=str(profile)))

    assert client.is_authenticated() is True


def test_is_authenticated_false_when_cookie_missing(tmp_path: Path) -> None:
    profile_dir = tmp_path / "auth" / "profile"
    (profile_dir / "Default").mkdir(parents=True, exist_ok=True)
    client = LinkedInMCPAuthClient(_config(user_data_dir=str(profile_dir)))

    assert client.is_authenticated() is False


def test_session_status_needs_login_when_incomplete(tmp_path: Path) -> None:
    profile = tmp_path / "auth" / "profile"
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    client = LinkedInMCPAuthClient(_config(user_data_dir=str(profile)))

    assert client.session_status() is LinkedInSessionStatus.NEEDS_LOGIN


def test_session_status_not_authenticated_when_state_unparseable(tmp_path: Path) -> None:
    profile = _build_session_tree(tmp_path, valid=False)
    client = LinkedInMCPAuthClient(_config(user_data_dir=str(profile)))

    assert client.session_status() is LinkedInSessionStatus.NEEDS_LOGIN


def test_session_status_authenticated(tmp_path: Path) -> None:
    profile = _build_session_tree(tmp_path)
    client = LinkedInMCPAuthClient(_config(user_data_dir=str(profile)))

    assert client.session_status() is LinkedInSessionStatus.AUTHENTICATED


def test_session_not_authenticated_when_profile_dir_inaccessible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Files exist but the profile dir's DACL denies the owner (WinError 5)."""
    profile = _build_session_tree(tmp_path)
    client = LinkedInMCPAuthClient(_config(user_data_dir=str(profile)))

    def _denied(path: Path) -> object:
        raise PermissionError(f"[WinError 5] Access is denied: '{path}'")

    monkeypatch.setattr(auth_module.os, "scandir", _denied)

    assert client.is_authenticated() is False
    assert client.session_status() is LinkedInSessionStatus.NEEDS_LOGIN


def test_session_detail_reports_unreadable_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profile = _build_session_tree(tmp_path)

    def _denied(path: Path) -> object:
        raise PermissionError(f"[WinError 5] Access is denied: '{path}'")

    monkeypatch.setattr(auth_module.os, "scandir", _denied)

    ready, detail = auth_module._session_ready(_config(user_data_dir=str(profile)))

    assert ready is False
    assert detail["profile_readable"] == "False"
    assert detail["ready"] == "False"


def test_session_status_error_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(config: LinkedInMCPConfig) -> tuple[bool, dict[str, str]]:
        raise OSError("boom")

    monkeypatch.setattr(auth_module, "_session_ready", _boom)
    client = LinkedInMCPAuthClient(_config())

    assert client.session_status() is LinkedInSessionStatus.ERROR


def test_login_uses_headed_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _stub_spawn(monkeypatch, _ok())
    client = LinkedInMCPAuthClient(_config(login_headed=True, cwd="server-dir"))

    assert client.login() is True
    assert captured["cwd"] == "server-dir"
    assert captured["timeout"] == 3600.0
    assert captured["mode"] == "login"
    args = captured["args"]
    assert "--login" in args
    assert "--no-headless" in args


def test_login_respects_headless_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _stub_spawn(monkeypatch, _ok())
    client = LinkedInMCPAuthClient(_config(login_headed=False))

    client.login()
    assert "--no-headless" not in captured["args"]


def test_login_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_spawn(monkeypatch, _ok(returncode=1))
    client = LinkedInMCPAuthClient(_config())

    assert client.login() is False


def test_login_raises_when_command_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_spawn(
        monkeypatch,
        ServerProcessResult(
            launched=False,
            returncode=None,
            timed_out=False,
            pid=None,
            stdout="",
            stderr="",
        ),
    )
    client = LinkedInMCPAuthClient(_config(command="no-such-python"))

    with pytest.raises(LinkedInAuthError, match="command not found"):
        client.login()


def test_login_raises_when_flow_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_spawn(monkeypatch, _ok(returncode=None, timed_out=True, pid=42))
    client = LinkedInMCPAuthClient(_config(login_timeout_seconds=30))

    with pytest.raises(LinkedInAuthError, match="did not complete"):
        client.login()


def test_spawn_captures_stdout_and_exit_code(tmp_path: Path) -> None:
    script = "import sys; print('hello-out'); print('hello-err', file=sys.stderr); sys.exit(0)"
    result = _spawn_server(
        [sys.executable, "-c", script], cwd=str(tmp_path), timeout=60, mode="login"
    )

    assert result.launched is True
    assert result.timed_out is False
    assert result.returncode == 0
    assert result.pid is not None
    assert "hello-out" in result.stdout
    assert "hello-err" in result.stderr


def test_spawn_reports_child_still_alive_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakePopen:
        pid: int = 999

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            raise auth_module.subprocess.TimeoutExpired(cmd=[], timeout=1.0)

        def poll(self) -> None:
            return None

        def kill(self) -> None:
            pass

    monkeypatch.setattr(auth_module.subprocess, "Popen", _FakePopen)
    result = _spawn_server(
        [sys.executable, "-c", ""],
        cwd=str(tmp_path),
        timeout=0.001,
        mode="serve",
    )

    assert result.launched is True
    assert result.timed_out is True
    assert result.returncode is None


def test_spawn_launch_failure_reports_not_launched(tmp_path: Path) -> None:
    result = _spawn_server(
        ["definitely-not-a-real-interpreter-xyz"], cwd=str(tmp_path), timeout=5, mode="serve"
    )

    assert result.launched is False
