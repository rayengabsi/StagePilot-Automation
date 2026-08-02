from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector


class _FakeHttpClient:
    """Minimal HTTP client test double returning a fixed body."""

    def __init__(self, text: str) -> None:
        """Initialize the fake with the response body."""
        self._text = text

    def get_text(
        self,
        _url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, object] | None = None,
    ) -> str:
        """Return the configured response body."""
        return self._text

    def get_json(
        self,
        _url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        """Unused for the RSS connector."""
        raise AssertionError("get_json should not be called for RSS feeds")


def _connector(xml: str) -> RssFeedConnector:
    """Build an RSS connector backed by a fake HTTP client."""
    return RssFeedConnector(Settings(), http_client=_FakeHttpClient(xml))


def test_rss_connector_parses_rss_items() -> None:
    """RSS connector should parse valid RSS items and skip incomplete ones."""
    xml = Path("tests/fixtures/rss/jobs.xml").read_text(encoding="utf-8")
    source = JobSourceConfig(
        id=1,
        name="Example RSS",
        type=JobSourceType.RSS_FEED,
        base_url="https://example.com/rss.xml",
    )

    jobs = _connector(xml).fetch(source)

    assert len(jobs) == 1
    assert jobs[0].external_id == "job-1"
    assert jobs[0].title == "Software Engineering PFE Internship"
    assert jobs[0].company == "Example RSS"


def test_rss_connector_parses_atom_entries() -> None:
    """RSS connector should also parse Atom feeds."""
    xml = Path("tests/fixtures/rss/jobs.atom").read_text(encoding="utf-8")
    source = JobSourceConfig(
        id=1,
        name="Example Atom",
        type=JobSourceType.RSS_FEED,
        base_url="https://example.com/atom.xml",
    )

    jobs = _connector(xml).fetch(source)

    assert len(jobs) == 1
    assert jobs[0].external_id == "atom-job-1"
    assert jobs[0].url == "https://example.com/jobs/atom-1"
    assert jobs[0].posted_at is not None
