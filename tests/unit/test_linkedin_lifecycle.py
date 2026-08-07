"""Unit tests for the LinkedIn MCP lifecycle management.

These exercise the state machine, startup/shutdown bounds, reuse semantics,
and crash recovery. A tiny fake client and an injectable readiness probe keep
them fast and deterministic; no real subprocess is spawned.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.infrastructure.linkedin_mcp.client import LinkedInMCPError
from app.infrastructure.linkedin_mcp.lifecycle import (
    LinkedInMCPLifecycle,
    LinkedInMCPLifecycleError,
    LinkedInMCPState,
)


class _FakeClient:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.pings = 0
        self.closed = False

    def ping(self, timeout: float | None) -> bool:
        self.pings += 1
        return self.ready


def _config(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "startup_timeout_seconds": 5.0,
        "shutdown_timeout_seconds": 1.0,
        "ready_poll_seconds": 0.0,
        "status_probe_timeout_seconds": 1.0,
        "command": "python",
        "cwd": ".",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _lifecycle(
    *, ready: bool = True, **overrides: object
) -> tuple[LinkedInMCPLifecycle, _FakeClient]:
    client = _FakeClient(ready=ready)

    def factory() -> _FakeClient:
        return client

    lc = LinkedInMCPLifecycle(
        _config(**overrides),
        client_factory=factory,
    )
    return lc, client


def test_startup_reaches_ready_state() -> None:
    lc, client = _lifecycle()
    lc.start()
    assert lc.state is LinkedInMCPState.READY
    assert lc.is_running() is True
    assert client.pings >= 1


def test_start_is_idempotent_reuses_client() -> None:
    lc, client = _lifecycle()
    lc.start()
    first = client
    lc.start()
    lc.start()
    assert lc.is_running() is True
    assert client is first


def test_startup_failure_is_structured_and_cleaned_up() -> None:
    def factory() -> object:
        raise RuntimeError("boom launch")

    lc = LinkedInMCPLifecycle(
        _config(),
        client_factory=factory,
        ready_probe=lambda: True,
    )
    with pytest.raises(LinkedInMCPLifecycleError) as excinfo:
        lc.start()
    assert excinfo.value.code in ("startup_failed", "startup_timeout")
    assert lc.state is LinkedInMCPState.ERROR


def test_startup_timeout_never_hangs() -> None:
    lc, client = _lifecycle(ready=False, startup_timeout_seconds=0.2)
    with pytest.raises(LinkedInMCPLifecycleError) as excinfo:
        lc.start()
    assert excinfo.value.code == "startup_timeout"
    assert lc.state is LinkedInMCPState.ERROR
    assert client.pings > 0


def test_graceful_shutdown_sets_stopped() -> None:
    lc, _client = _lifecycle()
    lc.start()
    lc.stop()
    assert lc.state is LinkedInMCPState.STOPPED
    assert lc.is_running() is False


def test_stop_when_already_stopped_is_noop() -> None:
    lc, _client = _lifecycle()
    lc.stop()
    assert lc.state is LinkedInMCPState.STOPPED


def test_restart_recovers_after_stop() -> None:
    lc, _client = _lifecycle()
    lc.start()
    lc.restart()
    assert lc.state is LinkedInMCPState.READY


def test_no_orphan_after_failed_start() -> None:
    lc, _client = _lifecycle(ready=False, startup_timeout_seconds=0.2)
    with pytest.raises(LinkedInMCPLifecycleError):
        lc.start()
    assert lc._client is None


def test_run_restarts_once_on_transient_failure() -> None:
    lc, _client = _lifecycle()
    lc.start()
    calls = {"n": 0}

    def operation() -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise LinkedInMCPError("connection dropped")
        return 42

    assert lc.run(operation) == 42
    assert calls["n"] == 2
    assert lc.is_running() is True


def test_run_raises_structured_error_after_recovery_fails() -> None:
    lc, _client = _lifecycle()
    lc.start()

    def operation() -> int:
        raise LinkedInMCPError("keeps dropping")

    with pytest.raises(LinkedInMCPLifecycleError) as excinfo:
        lc.run(operation)
    assert excinfo.value.code == "recovery_failed"


def test_restart_noop_preserves_state_when_running() -> None:
    lc, _client = _lifecycle()
    lc.start()
    lc.restart()
    assert lc.state is LinkedInMCPState.READY
