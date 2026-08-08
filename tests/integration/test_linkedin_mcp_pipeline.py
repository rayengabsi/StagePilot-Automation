"""Milestone 4: LinkedIn MCP jobs flow through the existing matching pipeline.

Demonstrates, end to end against the local protocol-shape stub MCP server:
  - jobs retrieved from LinkedIn MCP via ``search_jobs`` + ``get_job_details``
  - raw posting text parsed into structured fields
  - jobs normalized (ingested as persisted Job records)
  - match score calculated by the existing recommendation engine
  - explanation generated from explainable scoring artifacts
  - jobs filtered by the configured recommendation cutoff threshold
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.db.models.jobs import Job, JobSource, RawJob
from app.db.models.matching import JobMatch
from app.db.models.profile import (
    PreferenceRecord,
    ProfileVersionRecord,
    SkillRecord,
)
from app.db.models.profile import Profile as ProfileRecord
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.infrastructure.linkedin_mcp.notification_state import NotificationStateRepository
from app.infrastructure.telegram.notification import TelegramNotificationService
from app.services.linkedin_mcp_pipeline_service import (
    LinkedInFetchFailedError,
    LinkedInMCPPipelineService,
)
from app.services.linkedin_notify_service import LinkedInNotifyService
from app.shared.time import utc_now
from sqlalchemy.orm import Session

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STUB_SERVER = _REPO_ROOT / "scripts" / "stub_linkedin_mcp_server.py"


def _add_profile(session: Session) -> ProfileRecord:
    """Create an active profile with Python skills and a remote preference."""
    profile = ProfileRecord(active=True)
    session.add(profile)
    session.flush()
    session.add(
        ProfileVersionRecord(
            profile_id=profile.id,
            version_number=1,
            snapshot_json={"personal_info": {"full_name": "Test User", "location": "Paris"}},
            completeness_score=80.0,
            change_description="initial",
        )
    )
    session.add(SkillRecord(profile_id=profile.id, name="Python"))
    session.add(SkillRecord(profile_id=profile.id, name="Backend"))
    session.add(PreferenceRecord(profile_id=profile.id, remote_preference="hybrid"))
    session.commit()
    return profile


def _add_linkedin_source(session: Session, keywords: str | None = None) -> JobSource:
    """Create an active LinkedIn MCP source pointing at the stub server."""
    config: dict = {
        "search_tool": "search_jobs",
        "detail_tool": "get_job_details",
        "server_command": sys.executable,
        "server_args": [str(_STUB_SERVER)],
        "server_cwd": str(_REPO_ROOT),
    }
    if keywords:
        config["keywords"] = keywords
    source = JobSource(
        name="LinkedIn Stub",
        type=JobSourceType.LINKEDIN_MCP.value,
        base_url=sys.executable,
        config_json=config,
        is_active=True,
    )
    session.add(source)
    session.commit()
    return source


def _add_broken_linkedin_source(session: Session) -> JobSource:
    """Create an active LinkedIn MCP source whose server never starts.

    Used to simulate a failed real fetch: the connector raises, discovery
    marks the source failed, and the pipeline must stop instead of notifying
    from stored/historical jobs.
    """
    source = JobSource(
        name="LinkedIn Broken",
        type=JobSourceType.LINKEDIN_MCP.value,
        base_url="definitely-not-a-real-command",
        config_json={
            "search_tool": "search_jobs",
            "detail_tool": "get_job_details",
            "server_command": "definitely-not-a-real-command",
            "server_cwd": str(_REPO_ROOT),
        },
        is_active=True,
    )
    session.add(source)
    session.commit()
    return source


def _seed_historical_mock_job(session: Session, source: JobSource, *, tag: str, title: str) -> int:
    """Insert a stored job shaped like the leaked MOCK-101/MOCK-102 records.

    These records have a hard-filter-passing ``JobMatch`` — exactly the shape
    a stored job must have to be recommended — so any run that falls back to
    historical jobs would match and report them. Regression tests assert they
    can never reach Telegram.
    """
    url = f"https://www.linkedin.com/jobs/view/mock-{tag}"
    raw = RawJob(
        source_id=source.id,
        external_id=f"MOCK-{tag}",
        url=url,
        raw_payload_json={"job_id": f"MOCK-{tag}"},
        content_hash=f"hash-mock-{tag}",
        discovered_at=utc_now(),
    )
    session.add(raw)
    session.flush()
    job = Job(
        raw_job_id=raw.id,
        source_id=source.id,
        external_id=f"MOCK-{tag}",
        url=url,
        title=title,
        location="Tunis, Tunisia",
        requirements="Python",
        normalized_hash=f"norm-mock-{tag}",
    )
    session.add(job)
    session.flush()
    session.add(JobMatch(job_id=job.id, hard_filter_ok=True))
    session.commit()
    return job.id


def test_linkedin_job_flows_through_matching_pipeline(db_session: Session) -> None:
    """Fetched LinkedIn jobs are normalized, scored, explained, and filtered."""
    _add_profile(db_session)
    _add_linkedin_source(db_session)

    result = LinkedInMCPPipelineService(session=db_session).run()

    assert result.fetched >= 1
    assert result.inserted >= 1
    assert result.matched_total >= 1
    assert result.recommendations

    rec = result.recommendations[0]
    assert rec.final_score > 0
    assert rec.explanation
    assert "Software Engineer Intern" in rec.title
    assert rec.url == "https://www.linkedin.com/jobs/view/101/"
    assert rec.location
    assert result.cutoff == 30.0
    assert result.above_threshold + result.below_threshold == result.matched_total
    for item in result.recommendations:
        expected = item.final_score >= result.cutoff
        assert item.above_threshold == expected


def test_linkedin_mcp_threshold_keeps_only_above_cutoff(db_session: Session) -> None:
    """Raising the cutoff filters all recommendations below the threshold."""
    _add_profile(db_session)
    _add_linkedin_source(db_session)

    service = LinkedInMCPPipelineService(session=db_session, cutoff=10_000.0)

    result = service.run()

    if result.matched_total:
        assert result.above_threshold == 0
        assert result.below_threshold == result.matched_total
        assert all(not item.above_threshold for item in result.recommendations)


def test_linkedin_pipeline_requires_a_configured_source(db_session: Session) -> None:
    """Running without an active LinkedIn source raises a helpful error."""
    _add_profile(db_session)

    service = LinkedInMCPPipelineService(session=db_session)
    try:
        service.run()
    except SourceConfigError as exc:
        assert "add-linkedin-mcp" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected SourceConfigError")


class _FakeNotifier(TelegramNotificationService):
    """Notifier that records match URLs instead of reaching out to Telegram."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_linkedin_matches(self, recommendations: object) -> int:
        matches = [rec for rec in recommendations if rec.above_threshold]  # type: ignore[union-attr]
        self.sent = [rec.url for rec in matches]
        return len(self.sent)


def test_linkedin_notify_delivers_new_matches_once(db_session: Session) -> None:
    """The notify service delivers new matches and then deduplicates them."""
    _add_profile(db_session)
    _add_linkedin_source(db_session)

    repo = _InMemoryState()
    notifier = _FakeNotifier()
    service = LinkedInNotifyService(session=db_session, state_repo=repo, notifier=notifier)

    first = service.run()
    assert first.status == "ok"
    assert first.telegram_sent >= 1
    assert first.new_matches == first.telegram_sent
    assert first.telegram_sent == len(notifier.sent)

    # The second run re-fetches the same job and discovery reports it as a
    # duplicate, so this run inserted nothing and must not re-recommend the
    # stored job — a notification run only ever matches its current fetch.
    second = service.run()
    assert second.status == "ok"
    assert second.duplicates >= 1
    assert second.matched_total == 0
    assert second.new_matches == 0
    assert second.telegram_sent == 0
    assert second.already_notified == 0


class _InMemoryState(NotificationStateRepository):
    """In-memory notification state repo for dedup tests."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_notified(self, url: str) -> bool:
        return url in self._seen

    def mark_notified(self, url: str) -> None:
        self._seen.add(url)


def test_pipeline_raises_fetch_failed_when_source_fails(db_session: Session) -> None:
    """A failed real fetch raises instead of returning a stale-job result."""
    _add_profile(db_session)
    _add_broken_linkedin_source(db_session)

    service = LinkedInMCPPipelineService(session=db_session)
    try:
        service.run()
    except LinkedInFetchFailedError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected LinkedInFetchFailedError")


def test_notify_fetch_failure_never_sends_stored_mock_jobs(db_session: Session) -> None:
    """Stored MOCK-101/MOCK-102 jobs are never delivered when the fetch fails."""
    source = _add_broken_linkedin_source(db_session)
    _seed_historical_mock_job(db_session, source, tag="101", title="Stored Mock PFE")
    _seed_historical_mock_job(db_session, source, tag="102", title="Stored Mock Apprenticeship")

    notifier = _FakeNotifier()
    result = LinkedInNotifyService(
        session=db_session, state_repo=_InMemoryState(), notifier=notifier
    ).run()

    assert result.status == "error"
    assert result.fetched == 0
    assert result.matched_total == 0
    assert result.new_matches == 0
    assert result.telegram_sent == 0
    assert notifier.sent == []
    assert not any("mock-" in url for url in notifier.sent)


def test_notify_zero_fetched_never_sends_stored_mock_jobs(db_session: Session) -> None:
    """A successful zero-job fetch still never falls back to stored mock jobs."""
    source = _add_linkedin_source(db_session, keywords="zzzz-no-match-anything")
    _seed_historical_mock_job(db_session, source, tag="101", title="Stored Mock PFE")
    _seed_historical_mock_job(db_session, source, tag="102", title="Stored Mock Apprenticeship")

    notifier = _FakeNotifier()
    result = LinkedInNotifyService(
        session=db_session, state_repo=_InMemoryState(), notifier=notifier
    ).run()

    assert result.status == "no_jobs"
    assert result.fetched == 0
    assert result.telegram_sent == 0
    assert notifier.sent == []


def test_notify_success_sends_only_this_runs_jobs_not_stored_mock(db_session: Session) -> None:
    """A successful fetch delivers only this run's real jobs, never stored mocks."""
    _add_profile(db_session)
    source = _add_linkedin_source(db_session)
    _seed_historical_mock_job(db_session, source, tag="101", title="Stored Mock PFE")
    _seed_historical_mock_job(db_session, source, tag="102", title="Stored Mock Apprenticeship")

    notifier = _FakeNotifier()
    result = LinkedInNotifyService(
        session=db_session, state_repo=_InMemoryState(), notifier=notifier
    ).run()

    assert result.status == "ok"
    assert result.telegram_sent >= 1
    assert result.telegram_sent == len(notifier.sent)
    sent_urls = notifier.sent
    assert all(not url.endswith("mock-101") and not url.endswith("mock-102") for url in sent_urls)
    assert all(url.startswith("https://www.linkedin.com/jobs/view/") for url in sent_urls)
