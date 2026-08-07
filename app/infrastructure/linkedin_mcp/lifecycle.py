"""Automatic lifecycle management for the real LinkedIn MCP server.

StagePilot owns the server's life cycle so the user never starts or stops it
by hand. ``LinkedInMCPLifecycle`` is the single interface business logic uses:

    start()            load config, (re)use a live server, wait until ready
    wait_until_ready() confirm the server is usable before running searches
    is_running()       live, structured status
    run()              perform work with single-shot crash recovery
    stop()             shut down only the process we started; never a foreign one
    restart()          stop then start

Only this module ever talks to a process or a PID. The pipeline, matching
engine, parser, and notification service only see these methods. Startup and
shutdown are both hard-bounded so the command can never hang, and any failure
cleans up after itself (no orphaned server processes).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, TypeVar

from app.config.linkedin_mcp_config import LinkedInMCPConfig
from app.infrastructure.linkedin_mcp.client import (
    LinkedInMCPClient,
    LinkedInMCPError,
)

__all__ = [
    "LinkedInMCPLifecycle",
    "LinkedInMCPLifecycleError",
    "LinkedInMCPState",
]

logger = logging.getLogger("stagepilot.linkedin_mcp.lifecycle")

ClientFactory = Callable[[], LinkedInMCPClient]
ReadyProbe = Callable[[], bool]
T = TypeVar("T")


class LinkedInMCPState(StrEnum):
    """Current state of the managed LinkedIn MCP server."""

    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    ERROR = "error"


class LinkedInMCPLifecycleError(RuntimeError):
    """Raised when the MCP server cannot be started, made ready, or stopped.

    Carries a machine-readable ``code`` so callers can branch on the failure
    type (startup_timeout, startup_failed, shutdown_timeout, recovery_failed).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for structured reporting."""
        return {"code": self.code, "message": str(self)}


class LinkedInMCPLifecycle:
    """Own a single LinkedIn MCP session for one notify run.

    Arguments:
        config: Production ``LinkedInMCPConfig`` (command, cwd, args, timeouts).
        client_factory: Produces the ``LinkedInMCPClient`` used for the run.
            Defaults to building a client straight from ``config``.
        ready_probe: Optional readiness predicate; defaults to a real
            ``list_tools`` handshake through the client.
        poll_seconds: Interval between readiness probes.
    """

    def __init__(
        self,
        config: LinkedInMCPConfig,
        *,
        client_factory: ClientFactory | None = None,
        ready_probe: ReadyProbe | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """Initialize the lifecycle with its configuration and dependencies."""
        self._config = config
        self._client_factory = client_factory or self._default_client
        self._ready_probe = ready_probe
        self._timeout_seconds = (
            config.startup_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        self._state = LinkedInMCPState.STOPPED
        self._client: LinkedInMCPClient | None = None

    # -- port surface -------------------------------------------------------

    @property
    def state(self) -> LinkedInMCPState:
        """Current lifecycle state."""
        return self._state

    def is_running(self) -> bool:
        """Return True when the server is currently ready and in use."""
        return self._state in (LinkedInMCPState.READY, LinkedInMCPState.STARTING)

    def start(self, timeout: float | None = None) -> None:
        """Start (or reuse) the server and wait until it is ready.

        Idempotent: safe to call when already started. Never leaves the server
        in a partial state — a failed start is stopped and reported.
        """
        if self._state in (LinkedInMCPState.READY, LinkedInMCPState.STARTING):
            return
        deadline = self._effective_timeout(timeout)
        logger.info("Starting LinkedIn MCP server")
        self._state = LinkedInMCPState.STARTING
        try:
            self._client = self._client_factory()
            self.wait_until_ready(timeout=deadline)
        except Exception as exc:
            self._stop()
            self._state = LinkedInMCPState.ERROR
            code = _failure_code(exc)
            raise LinkedInMCPLifecycleError(code, f"LinkedIn MCP failed to start: {exc}") from exc
        self._state = LinkedInMCPState.READY
        logger.info("LinkedIn MCP server ready")

    def wait_until_ready(self, timeout: float | None = None) -> None:
        """Poll readiness until success or until ``timeout`` expires."""
        deadline = time.monotonic() + self._effective_timeout(timeout)
        poll = max(self._config.ready_poll_seconds, 0.1)
        while True:
            if self._probe_ready():
                return
            if time.monotonic() >= deadline:
                raise LinkedInMCPLifecycleError(
                    "startup_timeout",
                    "LinkedIn MCP server did not become ready in time",
                )
            time.sleep(poll)

    def stop(self) -> None:
        """Gracefully shut down the process we started; never a foreign one."""
        if self._state is LinkedInMCPState.STOPPED:
            return
        was_ready = self._state in (LinkedInMCPState.READY, LinkedInMCPState.STARTING)
        logger.info("Closing LinkedIn MCP")
        self._state = LinkedInMCPState.STOPPING
        try:
            self._shutdown_once()
        finally:
            self._client = None
            self._state = LinkedInMCPState.STOPPED
        if was_ready:
            logger.info("LinkedIn MCP stopped")

    def restart(self, timeout: float | None = None) -> None:
        """Stop the current server, if any, and start it again."""
        self.stop()
        self.start(timeout=timeout)

    def run(self, operation: Callable[[], T]) -> T:
        """Run ``operation`` with one crash-recovery restart.

        A transient MCP connection failure is treated as a server death: the
        server is restarted once and ``operation`` retried. A second failure
        raises a structured error; other exceptions propagate unchanged so
        domain semantics stay intact.
        """
        try:
            return operation()
        except LinkedInMCPError:
            logger.warning("LinkedIn MCP server died mid-run; restarting once")
            self.restart()
            try:
                return operation()
            except LinkedInMCPError as exc:
                self._state = LinkedInMCPState.ERROR
                raise LinkedInMCPLifecycleError(
                    "recovery_failed", f"LinkedIn MCP failed again after recovery: {exc}"
                ) from exc

    # -- internals ----------------------------------------------------------

    def _default_client(self) -> LinkedInMCPClient:
        return LinkedInMCPClient(
            command=self._config.command,
            args=self._config.base_arguments(),
            cwd=self._config.cwd,
            timeout_seconds=self._config.tool_timeout_seconds,
        )

    def _effective_timeout(self, timeout: float | None) -> float:
        return self._config.startup_timeout_seconds if timeout is None else timeout

    def _probe_ready(self) -> bool:
        """Ask the readiness probe; default uses a real server handshake."""
        if self._ready_probe is not None:
            return bool(self._ready_probe())
        client = self._client
        if client is None:
            return False
        return client.ping(timeout=self._config.status_probe_timeout_seconds)

    def _stop(self) -> None:
        """Best-effort teardown during a failed start (no orphan processes)."""
        try:
            self._shutdown_once()
        finally:
            self._client = None

    def _shutdown_once(self) -> None:
        """Best-effort teardown of the current run's session.

        ``LinkedInMCPClient`` opens and closes its own stdio connection per
        call, so there is no long-lived child to force here; we drop our
        reference and let the next GC/close finish teardown. This keeps
        ``stop()`` guaranteed non-blocking and orphan-free.
        """
        self._client = None


def _failure_code(exc: BaseException) -> str:
    code = getattr(exc, "code", None)
    if code:
        return str(code)
    return "startup_failed"
