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

from app.db.models.jobs import JobSource
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
from app.services.linkedin_mcp_pipeline_service import LinkedInMCPPipelineService
from app.services.linkedin_notify_service import LinkedInNotifyService
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

    second = service.run()
    assert second.status == "ok"
    assert second.telegram_sent == 0
    assert second.already_notified == first.above_threshold


class _InMemoryState(NotificationStateRepository):
    """In-memory notification state repo for dedup tests."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_notified(self, url: str) -> bool:
        return url in self._seen

    def mark_notified(self, url: str) -> None:
        self._seen.add(url)
