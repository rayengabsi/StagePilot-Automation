"""Unit tests for the LinkedIn connector's retry & recovery policy.

These tests exercise ``_with_retry``, ``_fetch_details``, and per-job recovery
with injected fake MCP clients, so they never touch a subprocess or a real
server.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from app.config.settings import get_settings
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import LinkedInSessionExpiredError
from app.infrastructure.job_sources.linkedin_mcp_connector import LinkedInMCPConnector
from app.infrastructure.linkedin_mcp.client import LinkedInMCPError


def _connector(**retry: object) -> LinkedInMCPConnector:
    server = SimpleNamespace(
        max_jobs=8,
        retry_attempts=retry.get("attempts", 3),
        retry_delay_seconds=retry.get("delay", 0.0),
        retry_backoff=retry.get("backoff", 2.0),
    )
    return LinkedInMCPConnector(get_settings(), mcp_config=server)  # type: ignore[arg-type]


def _source() -> JobSourceConfig:
    return JobSourceConfig(
        id=1,
        name="linkedin",
        type=JobSourceType.LINKEDIN_MCP,
        base_url="python",
        config={"search_tool": "search_jobs", "detail_tool": "get_job_details"},
    )


def _detail_posting(*text: str) -> dict[str, object]:
    return {
        "url": "https://www.linkedin.com/jobs/view/101/",
        "sections": {"job_posting": "\n".join(text)},
    }


def test_with_retry_returns_on_transient_success(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = _connector(attempts=3, delay=0.0)
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    calls = 0

    def _flaky() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LinkedInMCPError("boom")
        return 42

    result = connector._with_retry(_flaky)

    assert result == 42
    assert calls == 2
    assert sleeps == [0.0]  # one backoff step before the retry


def test_with_retry_raises_after_attempts_exhausted() -> None:
    connector = _connector(attempts=2, delay=0.0)

    def _boom() -> None:
        raise LinkedInMCPError("nope")

    with pytest.raises(LinkedInMCPError):
        connector._with_retry(_boom)


def test_with_retry_never_retries_expired_session() -> None:
    connector = _connector(attempts=3, delay=0.0)
    calls = 0

    def _expired() -> None:
        nonlocal calls
        calls += 1
        raise LinkedInSessionExpiredError("login required")

    with pytest.raises(LinkedInSessionExpiredError):
        connector._with_retry(_expired)
    assert calls == 1


def test_fetch_recovers_partial_details() -> None:
    class _BatchFailsOnce:
        def __init__(self) -> None:
            self.failures = 1

        def call_many(self, _calls: list[tuple[str, dict[str, object] | None]]) -> object:
            if self.failures:
                self.failures -= 1
                raise LinkedInMCPError("batch transient failure")
            return [_detail_posting("Tunis, Tunisia", "Engineer", "Acme", "About the job")]

        def call_tool(self, _name: str, _args: dict[str, object] | None = None) -> object:
            raise AssertionError("call_tool should not be needed on the happy path")

    connector = _connector(attempts=1, delay=0.0)
    jobs = connector._fetch_details(_BatchFailsOnce(), ["101"], "get_job_details")

    assert len(jobs) == 1
    assert jobs[0].external_id == "101"


def test_fetch_falls_back_to_per_job_recovery_when_batch_fails() -> None:
    detail = _detail_posting("Tunis, Tunisia", "Engineer", "Acme", "About the job")

    class _AlwaysFailsBatch:
        def call_many(self, _calls: list[tuple[str, dict[str, object] | None]]) -> object:
            raise LinkedInMCPError("batch always fails")

        def call_tool(self, _name: str, _args: dict[str, object] | None = None) -> object:
            return detail

    connector = _connector(attempts=1, delay=0.0)
    jobs = connector._fetch_details(_AlwaysFailsBatch(), ["101", "102"], "get_job_details")

    assert len(jobs) == 2
    assert all(isinstance(j, DiscoveredJob) for j in jobs)
    assert {j.external_id for j in jobs} == {"101", "102"}


def test_recover_details_skips_failing_jobs() -> None:
    good = _detail_posting("Tunis, Tunis", "Engineer", "Acme", "About the job")

    class _Selective:
        def call_tool(self, name: str, args: dict[str, object] | None = None) -> object:
            if args and args.get("job_id") == "666":
                raise LinkedInMCPError("job no longer exists")
            return good

    client = _Selective()
    connector = _connector(attempts=1, delay=0.0)

    jobs = connector._recover_details(client, ["101", "666"], "get_job_details")

    assert len(jobs) == 1
    assert isinstance(jobs[0], DiscoveredJob)
    assert jobs[0].external_id == "101"


def test_exhausted_delay_uses_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = _connector(attempts=2, delay=1.0, backoff=2.0)
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)

    def _boom() -> None:
        raise LinkedInMCPError("x")

    with pytest.raises(LinkedInMCPError):
        connector._with_retry(_boom)

    assert sleeps == [1.0, 2.0]
