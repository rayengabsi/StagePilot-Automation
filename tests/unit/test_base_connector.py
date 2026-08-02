from __future__ import annotations

from typing import Any, ClassVar

from app.config.settings import Settings
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.rate_limiter import RateLimiter
from app.shared.time import utc_now


class _EchoConnector(BaseJobSourceConnector):
    """Minimal connector that pages through a fixed item list."""

    source_type: ClassVar[JobSourceType] = JobSourceType.LEVER
    provider_name: ClassVar[str] = "echo"

    def __init__(self, items: list[dict[str, Any]], pages: int = 1) -> None:
        """Initialize the echo connector with controlled paging."""
        super().__init__(
            Settings(),
            http_client=_NoopHttp(),
            rate_limiter=RateLimiter(0.0),
        )
        self._items = items
        self._pages = pages

    def _initial_cursor(self, source: JobSourceConfig) -> int:
        """Start at page one."""
        return 1

    def _fetch_page(self, source: JobSourceConfig, cursor: int) -> PageResult:
        """Return one page of items with cursor advancement."""
        if cursor > self._pages:
            return PageResult(items=[], next_cursor=None)
        return PageResult(items=self._items, next_cursor=cursor + 1)

    def normalize(self, raw: dict[str, Any], source: JobSourceConfig) -> DiscoveredJob:
        """Return a minimal discovered job."""
        return DiscoveredJob(
            external_id=str(raw["id"]),
            url=raw["url"],
            title=raw["title"],
            company=raw.get("company"),
            location=None,
            description=None,
            raw_payload=raw,
            discovered_at=utc_now(),
        )


class _NoopHttp:
    """HTTP double that fails loudly if any request is attempted."""

    def get(self, *args: object, **kwargs: object) -> None:
        """Raise because base health checks are not exercised here."""
        raise AssertionError("Unexpected HTTP call")

    def get_json(self, *args: object, **kwargs: object) -> None:
        """Raise because base health checks are not exercised here."""
        raise AssertionError("Unexpected HTTP call")

    def get_text(self, *args: object, **kwargs: object) -> None:
        """Raise because base health checks are not exercised here."""
        raise AssertionError("Unexpected HTTP call")

    def post(self, *args: object, **kwargs: object) -> None:
        """Raise because base health checks are not exercised here."""
        raise AssertionError("Unexpected HTTP call")

    def post_json(self, *args: object, **kwargs: object) -> None:
        """Raise because base health checks are not exercised here."""
        raise AssertionError("Unexpected HTTP call")


def _source() -> JobSourceConfig:
    """Build a standard test source config."""
    return JobSourceConfig(
        id=1,
        name="Echo",
        type=JobSourceType.LEVER,
        base_url="https://example.com",
        config={},
    )


def test_fetch_loops_through_all_pages() -> None:
    """Fetch should accumulate items across every page."""
    item = {"id": "1", "url": "https://example.com/1", "title": "Job One"}
    connector = _EchoConnector([item], pages=3)

    jobs = connector.fetch(_source())

    assert len(jobs) == 3


def test_fetch_drops_none_normalizations() -> None:
    """Items that normalize to None should be skipped."""

    class _PartialConnector(_EchoConnector):
        def normalize(self, raw: dict[str, Any], source: JobSourceConfig) -> DiscoveredJob | None:
            """Return None for one of the two items."""
            if raw["id"] == "skip":
                return None
            return super().normalize(raw, source)

    items = [
        {"id": "skip", "url": "https://example.com/s", "title": "Skip"},
        {"id": "keep", "url": "https://example.com/k", "title": "Keep"},
    ]
    connector = _PartialConnector(items, pages=1)

    jobs = connector.fetch(_source())

    assert [j.external_id for j in jobs] == ["keep"]


def test_validate_requires_base_url() -> None:
    """Validate should report a missing base URL."""
    connector = _EchoConnector([], pages=1)
    source = JobSourceConfig(
        id=1,
        name="Broken",
        type=JobSourceType.LEVER,
        base_url="",
        config={},
    )

    errors = connector.validate(source)

    assert "base_url" in " ".join(errors)


def test_health_returns_unhealthy_on_failure() -> None:
    """Health should return an unhealthy result when requests fail."""

    class _ThrowingHttp(_NoopHttp):
        def get(self, *args: object, **kwargs: object) -> None:
            """Simulate a network failure."""
            raise ConnectionError("boom")

    connector = _EchoConnector([], pages=1)
    connector._http = _ThrowingHttp()

    health = connector.health(_source())

    assert health.status == "unhealthy"
    assert health.provider == "echo"
    assert health.message != ""
