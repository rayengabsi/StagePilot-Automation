from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import requests
from app.config.settings import Settings
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector
from pytest import MonkeyPatch


class _Response:
    """Minimal requests response test double."""

    status_code = 200

    def __init__(self, text: str) -> None:
        """Initialize the response with text content."""
        self.text = text

    def raise_for_status(self) -> None:
        """Simulate a successful HTTP response."""


def _fake_get(xml: str) -> Callable[..., _Response]:
    """Return a requests.get test double for static XML."""

    def _get(_url: str, **_kwargs: object) -> _Response:
        return _Response(xml)

    return _get


def test_rss_connector_parses_rss_items(monkeypatch: MonkeyPatch) -> None:
    """RSS connector should parse valid RSS items and skip incomplete ones."""
    xml = Path("tests/fixtures/rss/jobs.xml").read_text(encoding="utf-8")
    monkeypatch.setattr(requests, "get", _fake_get(xml))
    source = JobSourceConfig(
        id=1,
        name="Example RSS",
        type=JobSourceType.RSS_FEED,
        base_url="https://example.com/rss.xml",
    )

    jobs = RssFeedConnector(Settings()).fetch(source)

    assert len(jobs) == 1
    assert jobs[0].external_id == "job-1"
    assert jobs[0].title == "Software Engineering PFE Internship"
    assert jobs[0].company == "Example RSS"


def test_rss_connector_parses_atom_entries(monkeypatch: MonkeyPatch) -> None:
    """RSS connector should also parse Atom feeds."""
    xml = Path("tests/fixtures/rss/jobs.atom").read_text(encoding="utf-8")
    monkeypatch.setattr(requests, "get", _fake_get(xml))
    source = JobSourceConfig(
        id=1,
        name="Example Atom",
        type=JobSourceType.RSS_FEED,
        base_url="https://example.com/atom.xml",
    )

    jobs = RssFeedConnector(Settings()).fetch(source)

    assert len(jobs) == 1
    assert jobs[0].external_id == "atom-job-1"
    assert jobs[0].url == "https://example.com/jobs/atom-1"
    assert jobs[0].posted_at is not None
