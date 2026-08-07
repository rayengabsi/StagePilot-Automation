"""Diagnostics for the local StagePilot environment and its integrations.

``run_doctor`` runs a battery of read-only checks (environment, config,
database, Telegram, LinkedIn session, MCP server, optional dependencies) and
returns a list of ``DoctorCheck`` records. Every check is isolated: one failing
check never aborts the rest, and no check launches a real LinkedIn browser. It
stays decoupled from business logic and reports only what it observes.
"""

from __future__ import annotations

import importlib
import os
import platform as _platform
import shutil
from collections.abc import Callable
from dataclasses import dataclass

from app.config.linkedin_mcp_config import get_linkedin_mcp_config
from app.config.telegram_config import get_telegram_config
from app.infrastructure.linkedin_mcp.auth import (
    LinkedInMCPAuthClient,
    LinkedInSessionStatus,
)
from sqlalchemy import text


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """Outcome of a single diagnostic probe."""

    name: str
    ok: bool
    message: str

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "ok": self.ok, "message": self.message}


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Summary of a full diagnostic run."""

    checks: tuple[DoctorCheck, ...]
    python: str
    platform: str

    @property
    def all_ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "python": self.python,
            "platform": self.platform,
            "all_ok": self.all_ok,
            "checks": [check.to_dict() for check in self.checks],
        }


def run_doctor(
    session_factory: Callable[[], object] | None = None,
) -> DoctorReport:
    """Run every diagnostic probe and return a report (never raises)."""
    probes = (
        _probe_python_version,
        _probe_environment,
        _probe_database,
        _probe_telegram,
        _probe_linkedin_session,
        _probe_mcp_server,
        _probe_dependencies,
    )
    checks = [_guarded(probe, session_factory) for probe in probes]
    return DoctorReport(
        checks=tuple(checks),
        python=f"{_platform.python_version()} ({_platform.python_implementation()})",
        platform=str(_platform.platform()),
    )


def _guarded(
    probe: Callable[[Callable[[], object] | None], DoctorCheck],
    session_factory: Callable[[], object] | None,
) -> DoctorCheck:
    try:
        return probe(session_factory)
    except Exception as exc:
        return DoctorCheck(name=probe.__name__, ok=False, message=str(exc))


def _probe_python_version(_sf: Callable[[], object] | None) -> DoctorCheck:
    return DoctorCheck(
        name="python_version",
        ok=True,
        message=f"{_platform.python_version()} ({_platform.python_implementation()})",
    )


def _probe_environment(_sf: Callable[[], object] | None) -> DoctorCheck:
    cwd = os.getcwd()
    return DoctorCheck(
        name="environment",
        ok=os.access(cwd, os.W_OK),
        message=f"cwd={cwd}",
    )


def _probe_database(sf: Callable[[], object] | None) -> DoctorCheck:
    if sf is None:
        return DoctorCheck(name="database", ok=False, message="no session factory supplied")
    try:
        session = sf()
        session.execute(text("SELECT 1"))
        return DoctorCheck(name="database", ok=True, message="connectivity OK")
    except Exception as exc:
        return DoctorCheck(name="database", ok=False, message=f"unreachable: {exc}")


def _probe_telegram(_sf: Callable[[], object] | None) -> DoctorCheck:
    config = get_telegram_config()
    if not config.bot_token:
        return DoctorCheck(
            name="telegram",
            ok=False,
            message="bot token not configured (config/telegram.toml)",
        )
    if not config.allowed_chat_ids:
        return DoctorCheck(name="telegram", ok=False, message="no allowed_chat_ids configured")
    return DoctorCheck(
        name="telegram",
        ok=True,
        message=f"token set for {len(config.allowed_chat_ids)} allowed chat(s)",
    )


def _probe_linkedin_session(_sf: Callable[[], object] | None) -> DoctorCheck:
    try:
        config = get_linkedin_mcp_config()
    except Exception as exc:
        return DoctorCheck(name="linkedin_session", ok=False, message=f"config error: {exc}")

    if not _command_exists(config.command):
        return DoctorCheck(
            name="linkedin_session",
            ok=False,
            message=f"server python not found at {config.command}",
        )
    if not _session_cookie_present():
        return DoctorCheck(
            name="linkedin_session",
            ok=False,
            message="no saved LinkedIn session; run `stagepilot linkedin login`",
        )
    try:
        status = LinkedInMCPAuthClient(config).session_status(
            timeout=getattr(config, "status_probe_timeout_seconds", 20.0)
        )
    except Exception as exc:  # defensive: a probe must never crash the report
        return DoctorCheck(
            name="linkedin_session",
            ok=False,
            message=f"session validation failed: {exc}",
        )
    if status is LinkedInSessionStatus.AUTHENTICATED:
        return DoctorCheck(name="linkedin_session", ok=True, message="authenticated session")
    if status is LinkedInSessionStatus.NEEDS_LOGIN:
        return DoctorCheck(
            name="linkedin_session",
            ok=False,
            message="session needs re-login; run `stagepilot linkedin login`",
        )
    if status is LinkedInSessionStatus.TIMEOUT:
        return DoctorCheck(
            name="linkedin_session",
            ok=False,
            message="session check timed out; LinkedIn MCP server did not respond",
        )
    return DoctorCheck(
        name="linkedin_session",
        ok=False,
        message="saved session present but could not be validated",
    )


def _probe_mcp_server(_sf: Callable[[], object] | None) -> DoctorCheck:
    try:
        config = get_linkedin_mcp_config()
    except Exception as exc:
        return DoctorCheck(name="mcp_server", ok=False, message=f"config error: {exc}")
    if not _command_exists(config.command):
        return DoctorCheck(name="mcp_server", ok=False, message="server command not found")
    return DoctorCheck(
        name="mcp_server",
        ok=True,
        message=f"module={config.module} command={config.command}",
    )


def _probe_dependencies(_sf: Callable[[], object] | None) -> DoctorCheck:
    missing = [name for name in ("sqlalchemy", "telegram", "mcp") if not _importable(name)]
    if missing:
        return DoctorCheck(
            name="dependencies",
            ok=False,
            message="missing modules: " + ", ".join(missing),
        )
    return DoctorCheck(name="dependencies", ok=True, message="required modules importable")


def _command_exists(command: str) -> bool:
    if not command:
        return False
    return os.path.isfile(command) or shutil.which(command) is not None


def _session_cookie_present() -> bool:
    return os.path.isfile(os.path.expanduser("~/.linkedin-mcp/cookies.json"))


def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False
