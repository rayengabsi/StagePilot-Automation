"""Unit tests for the scheduler service.

The scheduler is tested strictly against the existing notify/pipeline service
boundary: every test injects a fake notify factory, so no LinkedIn MCP,
database, or Telegram is touched. These tests never sleep for real minutes.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.services.linkedin_notify_service import LinkedInNotifyResult
from app.services.scheduler_service import (
    SchedulerNotEnabledError,
    SchedulerService,
    SchedulerStateStore,
)

_SESSION = MagicMock()


@contextmanager
def _fake_scope() -> object:
    yield _SESSION


class FakeNotify:
    """Fake LinkedInNotifyService returning queued results or raising."""

    def __init__(self, *results: LinkedInNotifyResult | Exception, blocking: bool = False) -> None:
        self._results = list(results)
        self._blocking = blocking
        self.calls = 0
        self.sessions: list[object] = []
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(self) -> LinkedInNotifyResult:
        self.calls += 1
        result = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        if isinstance(result, Exception):
            raise result
        if self._blocking:
            self.entered.set()
            self.release.wait(timeout=5)
        return result


def _service(
    notify: FakeNotify,
    state_store: SchedulerStateStore,
    *,
    clock: Callable[[], float] | None = None,
    sleeper: Callable[[float], bool] | None = None,
    stop_event: threading.Event | None = None,
    enabled: bool = True,
    interval_minutes: int = 30,
) -> SchedulerService:
    from app.config.scheduler_config import SchedulerConfig

    def factory(session: object) -> FakeNotify:
        notify.sessions.append(session)
        return notify

    return SchedulerService(
        settings=MagicMock(),
        config=SchedulerConfig(enabled=enabled, interval_minutes=interval_minutes),
        state_store=state_store,
        notify_factory=factory,
        scope_factory=_fake_scope,
        clock=clock or (lambda: 1_000_000.0),
        sleeper=sleeper,
        stop_event=stop_event,
    )


def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            pytest.fail("condition not met before timeout")
        time.sleep(0.01)


def _store(tmp_path: Path) -> SchedulerStateStore:
    return SchedulerStateStore(tmp_path / "state.json")


# ---------------------------------------------------------------------------
# Test 1 - one-shot success
# ---------------------------------------------------------------------------


def test_once_calls_existing_notify_service_exactly_once(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok", fetched=2, telegram_sent=1))
    svc = _service(notify, _store(tmp_path))

    outcome = svc.run_once()

    assert outcome["status"] == "ok"
    assert outcome["success"] is True
    assert outcome["result"]["fetched"] == 2
    assert outcome["duration_seconds"] >= 0
    assert notify.calls == 1
    assert notify.sessions == [_SESSION]


def test_once_zero_fetched_is_a_valid_result_not_an_infra_failure(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="no_jobs", fetched=0))
    svc = _service(notify, _store(tmp_path))

    outcome = svc.run_once()

    assert outcome["status"] == "no_jobs"
    assert outcome["success"] is True


# ---------------------------------------------------------------------------
# Test 2 - one-shot failure (fail-closed, no stale-job fallback)
# ---------------------------------------------------------------------------


def test_once_failure_is_reported_and_never_claims_success(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="error", fetched=0, message="fetch failed"))
    store = _store(tmp_path)
    svc = _service(notify, store)

    outcome = svc.run_once()

    assert outcome["status"] == "error"
    assert outcome["success"] is False
    assert notify.calls == 1
    assert store.read()["last_run_status"] == "error"
    assert store.read()["last_run_success"] is False


def test_once_exception_is_contained_and_reported(tmp_path: Path) -> None:
    notify = FakeNotify(RuntimeError("db unavailable"))
    svc = _service(notify, _store(tmp_path))

    outcome = svc.run_once()

    assert outcome["status"] == "error"
    assert outcome["success"] is False
    assert "db unavailable" in str(outcome["result"]["message"])


def test_once_auth_required_is_not_success_and_reports_login(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="auth_required", message="session expired"))
    svc = _service(notify, _store(tmp_path))

    outcome = svc.run_once()

    assert outcome["status"] == "auth_required"
    assert outcome["success"] is False


# ---------------------------------------------------------------------------
# Test 3 - recurring execution on a controlled clock (no real sleeping)
# ---------------------------------------------------------------------------


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def test_recurring_loop_executes_multiple_times_without_real_sleeps(
    tmp_path: Path,
) -> None:
    notify = FakeNotify(
        LinkedInNotifyResult(status="no_jobs"),
        LinkedInNotifyResult(status="ok", fetched=4),
        LinkedInNotifyResult(status="ok", fetched=1),
        LinkedInNotifyResult(status="ok", fetched=0),
    )
    store = _store(tmp_path)
    clock = FakeClock()
    stop_event = threading.Event()
    slices = {"count": 0}
    max_slices = 25

    def sleeper(seconds: float) -> bool:
        clock.now += seconds
        slices["count"] += 1
        if slices["count"] >= max_slices:
            stop_event.set()
        return stop_event.is_set()

    svc = _service(
        notify,
        store,
        clock=clock,
        sleeper=sleeper,
        stop_event=stop_event,
        interval_minutes=1,
    )

    runs = svc.start(interval_minutes=1)

    assert runs == 3
    assert notify.calls == 3


def test_start_refuses_when_disabled(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok"))
    svc = _service(notify, _store(tmp_path), enabled=False)

    with pytest.raises(SchedulerNotEnabledError):
        svc.start()

    assert notify.calls == 0


def test_recurring_records_next_run_in_state(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok"))
    store = _store(tmp_path)
    clock = FakeClock()
    stop_event = threading.Event()

    def sleeper(_seconds: float) -> bool:
        stop_event.set()
        return True

    svc = _service(
        notify,
        store,
        clock=clock,
        sleeper=sleeper,
        stop_event=stop_event,
        interval_minutes=10,
    )

    svc.start(interval_minutes=10)

    data = store.read()
    assert data["running"] is False
    assert data["next_run_at"] is None
    assert data["interval_minutes"] == 10


# ---------------------------------------------------------------------------
# Test 4 - no overlapping executions
# ---------------------------------------------------------------------------


def test_concurrent_execution_is_skipped_not_duplicated(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok", fetched=1), blocking=True)
    store = _store(tmp_path)
    svc = _service(notify, store)

    first_outcome: dict[str, object] = {}
    thread = threading.Thread(target=lambda: first_outcome.update(svc.run_once()))
    thread.start()
    assert notify.entered.wait(timeout=5)

    second_outcome = svc.run_once()

    notify.release.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert notify.calls == 1
    assert second_outcome["status"] == "skipped_overlap"
    assert second_outcome["success"] is False
    assert first_outcome["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 5 - failure recovery across scheduled runs
# ---------------------------------------------------------------------------


def test_scheduler_survives_failed_run_and_next_run_succeeds(tmp_path: Path) -> None:
    notify = FakeNotify(
        RuntimeError("linkedin fetch exploded"),
        LinkedInNotifyResult(status="ok", fetched=3),
    )
    store = _store(tmp_path)
    svc = _service(notify, store)

    first = svc.run_once()
    second = svc.run_once()

    assert first["status"] == "error"
    assert first["success"] is False
    assert second["status"] == "ok"
    assert second["success"] is True
    assert notify.calls == 2
    assert store.read()["last_run_status"] == "ok"


def test_recurring_loop_keeps_running_after_failure(tmp_path: Path) -> None:
    notify = FakeNotify(
        RuntimeError("boom"),
        LinkedInNotifyResult(status="ok", fetched=2),
    )
    store = _store(tmp_path)
    clock = FakeClock()
    stop_event = threading.Event()

    def sleeper(seconds: float) -> bool:
        clock.now += seconds
        if notify.calls >= 2:
            stop_event.set()
            return True
        return False

    svc = _service(
        notify,
        store,
        clock=clock,
        sleeper=sleeper,
        stop_event=stop_event,
        interval_minutes=1,
    )

    runs = svc.start(interval_minutes=1)

    assert runs == 2
    assert notify.calls == 2
    assert store.read()["last_run_status"] == "ok"


# ---------------------------------------------------------------------------
# Test 6 - graceful shutdown
# ---------------------------------------------------------------------------


def test_stop_request_ends_loop_cleanly_and_marks_state_stopped(
    tmp_path: Path,
) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok"))
    store = _store(tmp_path)
    clock = FakeClock()
    stop_event = threading.Event()

    def sleeper(seconds: float) -> bool:
        clock.now += seconds
        return stop_event.is_set()

    svc = _service(
        notify,
        store,
        clock=clock,
        sleeper=sleeper,
        stop_event=stop_event,
        interval_minutes=60,
    )
    worker = threading.Thread(target=svc.start, kwargs={"interval_minutes": 60})
    worker.start()
    _wait_until(lambda: notify.calls == 1)

    stop_outcome = svc.request_stop()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert stop_outcome["stopping"] is True
    data = store.read()
    assert data["running"] is False
    assert data["stop_requested"] is False
    assert notify.calls == 1


def test_stop_flag_file_is_polled_by_the_loop(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok"), LinkedInNotifyResult(status="ok"))
    store = _store(tmp_path)
    clock = FakeClock()
    stop_event = threading.Event()

    def sleeper(seconds: float) -> bool:
        clock.now += seconds
        if store.stop_requested():
            stop_event.set()
            return True
        return False

    svc = _service(
        notify,
        store,
        clock=clock,
        sleeper=sleeper,
        stop_event=stop_event,
        interval_minutes=60,
    )

    def trigger_stop_after_first_wait() -> None:
        _wait_until(lambda: notify.calls == 1)
        store.request_stop()

    flag_writer = threading.Thread(target=trigger_stop_after_first_wait)
    flag_writer.start()
    runs = svc.start(interval_minutes=60)
    flag_writer.join(timeout=5)

    assert runs == 1
    assert notify.calls == 1
    assert store.read()["running"] is False


# ---------------------------------------------------------------------------
# Test 8 - pipeline boundary + status reporting
# ---------------------------------------------------------------------------


def test_scheduler_only_invokes_notify_service_boundary(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok", fetched=7))
    svc = _service(notify, _store(tmp_path))

    svc.run_once()

    assert notify.calls == 1
    assert notify.sessions == [_SESSION]


def test_status_snapshot_reports_config_and_last_run(tmp_path: Path) -> None:
    notify = FakeNotify(LinkedInNotifyResult(status="ok", fetched=5))
    store = _store(tmp_path)
    svc = _service(notify, store, enabled=False, interval_minutes=45)

    before = svc.status_snapshot()
    svc.run_once()
    after = svc.status_snapshot()

    assert before["enabled"] is False
    assert before["running"] is False
    assert before["interval_minutes"] == 45
    assert before["last_run_status"] is None
    assert after["enabled"] is False
    assert after["running"] is False
    assert after["last_run_status"] == "ok"
    assert after["last_run_success"] is True
    assert after["last_run_fetched"] == 5


def test_request_stop_when_not_running_is_idempotent(tmp_path: Path) -> None:
    svc = _service(FakeNotify(LinkedInNotifyResult(status="ok")), _store(tmp_path))

    outcome = svc.request_stop()

    assert outcome["stopping"] is False
    assert outcome["running"] is False


# ---------------------------------------------------------------------------
# State store persistence
# ---------------------------------------------------------------------------


def test_state_store_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    first = SchedulerStateStore(path)
    first.mark_running(pid=4242, started_at="2026-01-01T00:00:00+00:00", interval_minutes=30)
    first.record_run(
        status="ok",
        success=True,
        finished_at="2026-01-01T00:30:00+00:00",
        detail={"fetched": 1},
    )

    second = SchedulerStateStore(path)
    running, pid = second.is_running()

    assert pid == 4242
    assert second.read()["last_run_status"] == "ok"
    assert second.read()["last_run_detail"] == {"fetched": 1}
    assert running is False  # pid 4242 does not exist in this environment

    assert second.request_stop() is True
    assert second.stop_requested() is True
    second.mark_stopped()
    assert second.read()["running"] is False
    assert second.stop_requested() is False


def test_state_store_tolerates_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("not-json{", encoding="utf-8")
    store = SchedulerStateStore(path)

    assert store.read() == {}
    store.mark_stopped()
    assert store.read()["running"] is False


def test_state_file_is_valid_json(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.mark_running(pid=1, started_at="x", interval_minutes=5)

    payload = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))

    assert payload["pid"] == 1
