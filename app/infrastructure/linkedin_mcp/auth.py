"""Authentication plumbing for the real LinkedIn MCP server.

StagePilot drives the server's own CLI modes to manage its LinkedIn session:

- ``--status``: exits ``0`` when a valid session exists, non-zero otherwise.
- ``--login``: opens an interactive browser window, saves the session into the
  persistent profile directory (``~/.linkedin-mcp/profile`` by default), and
  exits.

This module exposes those two operations behind the small
``LinkedInSessionProvider`` port so the LinkedIn notify service can ask "am I
still authenticated / log me in" without knowing how the underlying server is
launched. Only the concrete adapter talks to the process.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.config.linkedin_mcp_config import LinkedInMCPConfig

__all__ = [
    "LinkedInAuthError",
    "LinkedInMCPAuthClient",
    "LinkedInSessionProvider",
]


class LinkedInAuthError(RuntimeError):
    """Raised when the LinkedIn session state cannot be determined or changed."""


class LinkedInSessionProvider(ABC):
    """Port for checking and establishing a logged-in LinkedIn session."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Return True when a valid authenticated session already exists."""

    @abstractmethod
    def login(self) -> bool:
        """Run the interactive one-time login flow and persist the session."""


class LinkedInMCPAuthClient(LinkedInSessionProvider):
    """Session management on top of the real ``linkedin_mcp_server`` CLI."""

    def __init__(self, config: LinkedInMCPConfig) -> None:
        self._config = config

    def is_authenticated(self) -> bool:
        """Check the persisted session via ``--status`` (exit 0 = valid)."""
        args = self._command("--status")
        returncode = self._run(args, timeout=self._config.status_timeout_seconds)
        return returncode == 0

    def login(self) -> bool:
        """Run the interactive, headed login flow and persist the session."""
        args = self._command("--login")
        if self._config.login_headed:
            args.append("--no-headless")
        returncode = self._run(args, timeout=self._config.login_timeout_seconds)
        return returncode == 0

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

    @staticmethod
    def _run(args: Sequence[str], *, timeout: float) -> int:
        """Run the server subprocess and return its exit code.

        Raises ``LinkedInAuthError`` only when the process cannot be started or
        exceeds the timeout; a non-zero exit code (e.g. "session file missing")
        is returned as-is so the caller can branch on it.
        """
        try:
            result = subprocess.run(  # noqa: S603 - command comes from trusted config
                list(args),
                capture_output=True,
                text=True,
                timeout=None if timeout <= 0 else timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            msg = f"LinkedIn MCP command not found: {args[0]}"
            raise LinkedInAuthError(msg) from exc
        except subprocess.TimeoutExpired as exc:
            raise LinkedInAuthError(
                f"LinkedIn MCP {args[3] if len(args) > 3 else 'command'} timed out"
            ) from exc
        return result.returncode
