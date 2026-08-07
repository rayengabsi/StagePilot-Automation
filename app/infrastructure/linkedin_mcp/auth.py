"""Authentication plumbing for the real LinkedIn MCP server.

StagePilot drives the server the way the server itself is designed to be
driven, signalling two separate things:

- **An authenticated session is the server's persisted files.** When a login
  completes, ``linkedin_mcp_server`` writes the socket source session into
  ``<profile-parent>/cookies.json`` plus ``source-state.json`` and a populated
  browser profile directory.  ``bootstrap._auth_ready`` — the gate the server
  itself uses for "do I have a session" — checks exactly those three.  This is
  the real "am I authenticated" signal: it needs no browser, no subprocess,
  and no timeout.

- **A login completes when the ``--login`` one-shot exits 0.**  ``--login``
  opens a headed browser, *blocks* for manual authentication (2FA/captcha),
  persists the session, then ``sys.exit(0)``.  The exit code is the server's
  own "login complete / login failed" signal.

The concrete adapter below exposes that flow through the small
``LinkedInSessionProvider`` port so the notify service and `doctor` can ask
"am I still authenticated / log me in" without knowing how the real server is
launched.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shlex
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.config.linkedin_mcp_config import LinkedInMCPConfig

logger = logging.getLogger(__name__)

__all__ = [
    "LinkedInAuthError",
    "LinkedInMCPAuthClient",
    "LinkedInSessionProvider",
    "LinkedInSessionStatus",
]

_DEFAULT_PROFILE_DIR = "~/.linkedin-mcp/profile"
_COOKIE_FILE = "cookies.json"
_SOURCE_STATE_FILE = "source-state.json"


class LinkedInAuthError(RuntimeError):
    """Raised when the LinkedIn session state cannot be determined or changed."""


class LinkedInSessionStatus(StrEnum):
    """Structured outcome of a session check; never a bare boolean."""

    AUTHENTICATED = "authenticated"
    NEEDS_LOGIN = "needs_login"
    TIMEOUT = "timeout"
    ERROR = "error"


class LinkedInSessionProvider(ABC):
    """Port for checking and establishing a logged-in LinkedIn session."""

    @abstractmethod
    def session_status(self, *, timeout: float | None = None) -> LinkedInSessionStatus:
        """Return the structured session state without ever blocking forever."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Return True when a valid authenticated session already exists."""

    @abstractmethod
    def login(self) -> bool:
        """Run the interactive one-time login flow and persist the session."""


@dataclass(frozen=True, slots=True)
class ServerProcessResult:
    """Outcome of one launched server subprocess, for diagnosis and testing."""

    launched: bool
    returncode: int | None
    timed_out: bool
    pid: int | None
    stdout: str
    stderr: str


def _session_files(config: LinkedInMCPConfig) -> tuple[Path, Path, Path]:
    """Return ``(profile_dir, cookies_path, source_state_path)`` regardless of OS.

    These are the server's own auth-artifact locations: the profile directory
    plus two sibling files the server writes when a login succeeds.
    """
    profile = (
        Path(os.path.expanduser(config.user_data_dir))
        if config.user_data_dir
        else Path(os.path.expanduser(_DEFAULT_PROFILE_DIR))
    )
    auth_root = profile.parent
    return profile, auth_root / _COOKIE_FILE, auth_root / _SOURCE_STATE_FILE


def _session_ready(config: LinkedInMCPConfig) -> tuple[bool, dict[str, str]]:
    """Mirror ``linkedin_mcp_server.bootstrap._auth_ready`` on the persisted files.

    Returns ``(ready, detail)`` where ``detail`` records the evaluatable paths
    for the debug log. Raises nothing; an unreadable tree reports ``ready`` as
    False instead of crashing the caller.

    The profile directory is only required to *exist*: the server hardens its
    ACL so the directory itself refuses directory listing (Windows), even to the
    owner, while the two sibling auth files stay readable by name. Checking
    those files is therefore the reliable signal, and does not need to enumerate
    the profile directory.
    """
    try:
        profile, cookies, source_state = _session_files(config)
        profile_ok = profile.is_dir()
        cookies_ok = cookies.is_file() and cookies.stat().st_size > 0
        source_state_ok = source_state.is_file()
        ready = profile_ok and cookies_ok and source_state_ok
        if ready:
            try:
                state = json.loads(source_state.read_text(encoding="utf-8"))
                ready = isinstance(state, dict) and bool(state)
            except (OSError, ValueError):
                ready = False
        if ready:
            try:
                cookie_data = json.loads(cookies.read_text(encoding="utf-8"))
                ready = isinstance(cookie_data, list) and len(cookie_data) > 0
            except (OSError, ValueError):
                ready = False
        detail = {
            "profile": str(profile),
            "profile_exists": str(profile_ok),
            "cookie_file": str(cookies),
            "cookie_ready": str(cookies_ok),
            "source_state": str(source_state),
            "source_state_ready": str(source_state_ok),
            "ready": str(ready),
        }
        return ready, detail
    except OSError as exc:
        return False, {"error": str(exc)}


def _spawn_server(
    args: Sequence[str],
    *,
    cwd: str,
    timeout: float,
    mode: str,
) -> ServerProcessResult:
    """Run a server one-shot to *files* and return its outcome.

    The output is captured to temp files rather than pipes.  A denoted-headed
    login spawns Chromium children that inherit the handle: with a pipe, those
    grandchildren hold the read end open and ``wait()``/``communicate()`` never
    see EOF, so the process "waits forever after login" even though the server
    already called ``sys.exit``.  A plain-file handle dies with the child, so
    the process' real exit signal is observed.
    """
    quoted = " ".join(shlex.quote(str(a)) for a in args)
    logger.debug("[%s] spawn cmd=%s cwd=%r timeout=%.0fs", mode, quoted, cwd, timeout)
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
    with tempfile.TemporaryDirectory(prefix="stagepilot-linkedin-") as tmp:
        stdout_path = Path(tmp) / "stdout.log"
        stderr_path = Path(tmp) / "stderr.log"
        try:
            stdout_file = stdout_path.open("w", encoding="utf-8")
            stderr_file = stderr_path.open("w", encoding="utf-8")
        except OSError as exc:
            logger.debug("[%s] spawn failed to open capture files: %s", mode, exc)
            return ServerProcessResult(
                launched=False, returncode=None, timed_out=False, pid=None, stdout="", stderr=""
            )
        try:
            try:
                proc = subprocess.Popen(  # noqa: S603 - command from trusted config
                    [str(a) for a in args],
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    close_fds=True,
                    creationflags=flags,
                )
            except OSError as exc:
                logger.debug("[%s] spawn launch failed: %s", mode, exc)
                return ServerProcessResult(
                    launched=False, returncode=None, timed_out=False, pid=None, stdout="", stderr=""
                )
            logger.debug("[%s] pid=%s", mode, proc.pid)

            deadline = None if timeout <= 0 else time.monotonic() + timeout
            timed_out = False
            returncode: int | None = None
            while True:
                if deadline is None:
                    with contextlib.suppress(OSError):
                        returncode = proc.wait()
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    returncode = proc.poll()
                    alive = returncode is None
                    logger.debug(
                        "[%s] timeout after %.0fs alive_after_timeout=%s pid=%s",
                        mode,
                        timeout,
                        alive,
                        proc.pid,
                    )
                    if alive:
                        proc.kill()
                        with contextlib.suppress(subprocess.TimeoutExpired):
                            proc.wait(timeout=10)
                    break
                try:
                    returncode = proc.wait(timeout=remaining)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            stdout_file.close()
            stderr_file.close()

        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        logger.debug(
            "[%s] exit=%r timed_out=%s pid=%s",
            mode,
            returncode,
            timed_out,
            getattr(proc, "pid", None),
        )
        if stdout:
            logger.debug("[%s] stdout:\n%s", mode, _tail(stdout))
        if stderr:
            logger.debug("[%s] stderr:\n%s", mode, _tail(stderr))
        return ServerProcessResult(
            launched=True,
            returncode=returncode,
            timed_out=timed_out,
            pid=proc.pid,
            stdout=stdout,
            stderr=stderr,
        )


def _tail(text: str, limit: int = 200) -> str:
    """Trim to the last ``limit`` lines for a digestible debug log line."""
    lines = text.rstrip("\n").split("\n")
    return "\n".join(lines[-limit:]) if len(lines) > limit else text


class LinkedInMCPAuthClient(LinkedInSessionProvider):
    """Session management on top of the real ``linkedin_mcp_server``.

    Auth status reads the server's persisted session files — the same gate the
    server uses — so checking never boots a browser and never blocks.  Login
    drives the server's own ``--login`` one-shot (no piped output, so its real
    exit code is observed instead of hanging on a Chromium child).
    """

    def __init__(self, config: LinkedInMCPConfig) -> None:
        self._config = config

    def is_authenticated(self) -> bool:
        ready, detail = _session_ready(self._config)
        logger.debug("[status] %s", " ".join(f"{k}={v}" for k, v in detail.items()))
        return ready

    def session_status(self, *, timeout: float | None = None) -> LinkedInSessionStatus:  # noqa: ARG002 - interface parity
        """Return the persisted-session state; never blocks, never raises."""
        try:
            ready, detail = _session_ready(self._config)
        except OSError as exc:
            logger.debug("[status] error inspecting session files: %s", exc)
            return LinkedInSessionStatus.ERROR
        logger.debug("[status] %s", " ".join(f"{k}={v}" for k, v in detail.items()))
        return LinkedInSessionStatus.AUTHENTICATED if ready else LinkedInSessionStatus.NEEDS_LOGIN

    def login(self) -> bool:
        """Run the server's ``--login`` flow and persist the session."""
        args = self._command("--login")
        if self._config.login_headed:
            args.append("--no-headless")
        result = _spawn_server(
            list(args),
            cwd=self._config.cwd,
            timeout=self._config.login_timeout_seconds,
            mode="login",
        )
        if not result.launched:
            raise LinkedInAuthError(f"LinkedIn MCP command not found: {args[0]}")
        if result.timed_out:
            raise LinkedInAuthError(
                "LinkedIn MCP login did not complete within "
                f"{self._config.login_timeout_seconds:.0f}s "
                f"(pid {result.pid} was still alive); the session may be mid-authentication"
            )
        return result.returncode == 0

    def _command(self, *extra: str) -> list[str]:
        """Build ``python -m linkedin_mcp_server <extra>``."""
        args: list[str] = [
            self._config.command,
            "-m",
            self._config.module,
            *extra,
        ]
        if self._config.log_level:
            args.extend(["--log-level", self._config.log_level])
        if self._config.user_data_dir:
            args.extend(["--user-data-dir", self._config.user_data_dir])
        return args
