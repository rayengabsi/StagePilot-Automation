"""Scheduler that executes the existing LinkedIn notification pipeline.

The scheduler is a thin orchestrator: it owns *when* the pipeline runs, never
*how* the pipeline works. Every execution delegates to
:class:`app.services.linkedin_notify_service.LinkedInNotifyService`, which
remains the single source of truth for

CV/profile -> LinkedIn MCP -> discovery -> user filter -> matching ->
deduplication -> Telegram.

Guarantees:

- at most one pipeline execution runs at a time (in-process guard);
- a failed run never kills the loop; the next scheduled run proceeds;
- ``fetched = 0`` (``no_jobs``) is a valid, successful outcome;
- LinkedIn failures stay fail-closed: no historical/DB job fallback;
- shutdown is clean: no new run starts once a stop is requested and per-run
  resources (DB engine) are released.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config.scheduler_config import SchedulerConfig, get_scheduler_config
from app.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.services.linkedin_notify_service import LinkedInNotifyService

logger = logging.getLogger(__name__)

STOP_POLL_SECONDS = 5.0
_SUCCESS_STATUSES = frozenset({"ok", "no_jobs"})
_STATE_VERSION = 1


class SchedulerNotEnabledError(RuntimeError):
    """Raised when starting a scheduler whose configuration is disabled."""


def _iso_now(timestamp: float) -> str:
    """Format an epoch timestamp as an ISO-8601 UTC string."""
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


class SchedulerStateStore:
    """Tiny JSON file persisting scheduler runtime state for status/stop.

    The scheduler is intentionally single-process; this store exists only so
    that separate CLI invocations (``status`` / ``stop``) can observe whether a
    scheduler is running, when it last ran, and request a graceful stop.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> dict[str, Any]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _update(self, **fields: object) -> None:
        data = self.read()
        if not data or data.get("version") != _STATE_VERSION:
            data = {"version": _STATE_VERSION}
        data.update(fields)
        self._write(data)

    def mark_running(self, *, pid: int, started_at: str, interval_minutes: int) -> None:
        self._update(
            running=True,
            pid=pid,
            started_at=started_at,
            interval_minutes=interval_minutes,
            stop_requested=False,
        )

    def record_run(
        self,
        *,
        status: str,
        success: bool | None,
        finished_at: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self._update(
            last_run_status=status,
            last_run_success=success,
            last_run_at=finished_at,
            last_run_detail=detail,
        )

    def set_next_run(self, next_run_at: str | None) -> None:
        self._update(next_run_at=next_run_at)

    def request_stop(self) -> bool:
        """Flag a running scheduler to stop. Returns True if one was running."""
        was_running = bool(self.read().get("running"))
        self._update(stop_requested=True)
        return was_running

    def clear_stop_request(self) -> None:
        self._update(stop_requested=False)

    def mark_stopped(self) -> None:
        self._update(running=False, pid=None, next_run_at=None, stop_requested=False)

    def stop_requested(self) -> bool:
        return bool(self.read().get("stop_requested"))

    def is_running(self) -> tuple[bool, int | None]:
        data = self.read()
        pid = data.get("pid")
        if not data.get("running") or not isinstance(pid, int):
            return False, None
        return _pid_alive(pid), pid


def _pid_alive(pid: int) -> bool:
    """Check process liveness without signaling on POSIX or killing on Windows."""
    if sys.platform == "win32":
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SchedulerService:
    """Execute the existing LinkedIn notify pipeline on a configurable interval."""

    def __init__(
        self,
        settings: Settings | None = None,
        config: SchedulerConfig | None = None,
        state_store: SchedulerStateStore | None = None,
        notify_factory: Callable[[Session], LinkedInNotifyService] | None = None,
        scope_factory: Callable[[], AbstractContextManager[Session]] | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], bool] | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._config = config or get_scheduler_config()
        self._state = state_store or SchedulerStateStore(Path("data/scheduler/state.json"))
        self._notify_factory = notify_factory or self._default_notify_factory
        self._scope_factory = scope_factory or self._default_scope_factory
        self._clock = clock
        self._sleeper = sleeper
        self._stop_event = stop_event or threading.Event()
        self._execution_lock = threading.Lock()
        self._signal_handlers: dict[int, Any] = {}

    # ------------------------------------------------------------------
    # One-shot execution
    # ------------------------------------------------------------------

    def run_once(self) -> dict[str, Any]:
        """Run the LinkedIn notification pipeline exactly once.

        Returns a JSON-serializable outcome. A concurrent execution is skipped
        (never queued twice); any failure is reported, never raised.
        """
        acquired = self._execution_lock.acquire(blocking=False)
        if not acquired:
            logger.warning("scheduled_execution_skipped reason=overlap previous_run_active=true")
            finished_at = _iso_now(self._clock())
            self._state.record_run(
                status="skipped_overlap",
                success=False,
                finished_at=finished_at,
                detail={"message": "A pipeline execution was already active."},
            )
            return {
                "status": "skipped_overlap",
                "success": False,
                "finished_at": finished_at,
                "message": "A pipeline execution was already active; skipped.",
            }
        started = self._clock()
        try:
            try:
                outcome = self._execute_once()
            except Exception as exc:
                logger.exception("scheduled_execution_failed")
                outcome = {
                    "status": "error",
                    "success": False,
                    "result": {"status": "error", "message": str(exc)},
                }
            duration = round(self._clock() - started, 3)
            result_payload = outcome.get("result")
            finished = {
                "status": outcome["status"],
                "success": bool(outcome.get("success")),
                "duration_seconds": duration,
                "finished_at": _iso_now(self._clock()),
                "result": result_payload,
            }
            self._state.record_run(
                status=outcome["status"],
                success=finished["success"],
                finished_at=finished["finished_at"],
                detail=result_payload if isinstance(result_payload, dict) else None,
            )
            if finished["success"]:
                logger.info(
                    "scheduled_execution_completed",
                    extra={
                        "status": outcome["status"],
                        "duration_seconds": duration,
                        "fetched": (result_payload or {}).get("fetched"),
                        "telegram_sent": (result_payload or {}).get("telegram_sent"),
                    },
                )
            else:
                logger.error(
                    "scheduled_execution_failed",
                    extra={"status": outcome["status"], "duration_seconds": duration},
                )
            return finished
        finally:
            self._execution_lock.release()

    def _execute_once(self) -> dict[str, Any]:
        with self._scope_factory() as session:
            service = self._notify_factory(session)
            notify_result = service.run()
        payload: dict[str, Any]
        payload = (
            notify_result.to_dict() if hasattr(notify_result, "to_dict") else dict(notify_result)
        )
        status = str(payload.get("status", "ok"))
        return {"status": status, "success": status in _SUCCESS_STATUSES, "result": payload}

    # ------------------------------------------------------------------
    # Recurring execution
    # ------------------------------------------------------------------

    def start(self, interval_minutes: int | None = None) -> int:
        """Run the pipeline every ``interval_minutes`` until stopped (blocking).

        Returns the number of executions attempted. Raises
        :class:`SchedulerNotEnabledError` when the configuration disables the
        scheduler.
        """
        if not self._config.enabled:
            raise SchedulerNotEnabledError(
                "Scheduler is disabled (config/scheduler.toml [scheduler].enabled). "
                "Set enabled = true, then run `stagepilot scheduler start`."
            )
        minutes = (
            interval_minutes if interval_minutes is not None else self._config.interval_minutes
        )
        if minutes < 1:
            raise SchedulerNotEnabledError(f"Interval must be >= 1 minute, got {minutes!r}.")
        seconds = minutes * 60

        self._stop_event.clear()
        self._state.clear_stop_request()
        self._state.mark_running(
            pid=os.getpid(), started_at=_iso_now(self._clock()), interval_minutes=minutes
        )
        logger.info(
            "scheduler_started",
            extra={"interval_minutes": minutes, "pid": os.getpid()},
        )
        runs = 0
        self._install_signal_handlers()
        try:
            while not self._stop_requested():
                self.run_once()
                runs += 1
                if self._stop_requested():
                    break
                self._wait_interval(seconds)
        finally:
            self._restore_signal_handlers()
            self._state.mark_stopped()
            logger.info("scheduler_stopped", extra={"runs": runs})
        return runs

    def _wait_interval(self, seconds: int) -> None:
        deadline = self._clock() + seconds
        self._state.set_next_run(_iso_now(deadline))
        while not self._stop_requested():
            remaining = deadline - self._clock()
            if remaining <= 0:
                break
            slice_seconds = min(STOP_POLL_SECONDS, remaining)
            if self._sleep(slice_seconds):
                break
        self._state.set_next_run(None)

    def _sleep(self, seconds: float) -> bool:
        """Sleep in interruptible slices; return True when a stop was requested."""
        if self._sleeper is not None:
            return bool(self._sleeper(seconds))
        return self._stop_event.wait(seconds)

    def _stop_requested(self) -> bool:
        return self._stop_event.is_set() or self._state.stop_requested()

    # ------------------------------------------------------------------
    # Status and shutdown
    # ------------------------------------------------------------------

    def status_snapshot(self) -> dict[str, Any]:
        """Report configuration and last-run state for `scheduler status`."""
        running, pid = self._state.is_running()
        data = self._state.read()
        detail = data.get("last_run_detail")
        return {
            "enabled": self._config.enabled,
            "running": running,
            "pid": pid if running else None,
            "interval_minutes": data.get("interval_minutes")
            if running
            else self._config.interval_minutes,
            "started_at": data.get("started_at"),
            "last_run_status": data.get("last_run_status"),
            "last_run_success": data.get("last_run_success"),
            "last_run_at": data.get("last_run_at"),
            "last_run_fetched": detail.get("fetched") if isinstance(detail, dict) else None,
            "next_run_at": data.get("next_run_at"),
            "stop_requested": bool(data.get("stop_requested")),
        }

    def request_stop(self) -> dict[str, Any]:
        """Ask a running scheduler to shut down cleanly."""
        running, pid = self._state.is_running()
        if not running:
            return {"stopping": False, "running": False, "message": "Scheduler is not running."}
        self._state.request_stop()
        if pid is not None and pid != os.getpid():
            self._signal_process(pid)
        else:
            self._stop_event.set()
        logger.info("scheduler_stop_requested", extra={"pid": pid})
        return {
            "stopping": True,
            "running": True,
            "pid": pid,
            "message": "Stop requested; the scheduler will finish cleanly.",
        }

    @staticmethod
    def _signal_process(pid: int) -> None:
        if sys.platform == "win32":
            # os.kill on Windows terminates forcefully; rely on the polled
            # stop flag instead so the loop can shut down cleanly.
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            logger.warning("scheduler_stop_signal_failed", extra={"pid": pid})

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _install_signal_handlers(self) -> None:
        def _handler(_signum: int, _frame: object) -> None:
            self._stop_event.set()

        for name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            try:
                self._signal_handlers[sig] = signal.signal(sig, _handler)
            except (ValueError, OSError):
                continue

    def _restore_signal_handlers(self) -> None:
        for sig, handler in self._signal_handlers.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                continue
        self._signal_handlers.clear()

    # ------------------------------------------------------------------
    # Production defaults
    # ------------------------------------------------------------------

    def _default_scope_factory(self) -> AbstractContextManager[Session]:
        from app.db.session import create_database_engine, create_session_factory, session_scope

        engine = create_database_engine(self._settings)

        @contextmanager
        def _scope() -> Iterator[Session]:
            try:
                session_factory = create_session_factory(engine)
                with session_scope(session_factory) as session:
                    yield session
            finally:
                engine.dispose()

        return _scope()

    @staticmethod
    def _default_notify_factory(session: Session) -> LinkedInNotifyService:
        from app.config.linkedin_mcp_config import get_linkedin_mcp_config
        from app.infrastructure.linkedin_mcp.lifecycle import LinkedInMCPLifecycle
        from app.services.linkedin_notify_service import LinkedInNotifyService

        return LinkedInNotifyService(
            session=session,
            lifecycle=LinkedInMCPLifecycle(get_linkedin_mcp_config()),
        )
