"""User-controlled job filter stage integrated with discovery and delivery.

Covers:
  - the filter stage runs only on the current run's inserted jobs,
  - filtered jobs never reach matching, recommendation, or Telegram delivery,
  - the run summaries expose ``filtered`` and ``filter_rejection_breakdown``,
  - an empty filter config is a clean pass-through,
  - stored MOCK-101/MOCK-102 jobs are never delivered under active filters.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.config.settings import FilterRules
from app.db.models.jobs import Job, JobSource, RawJob
from app.db.models.matching import JobMatch
from app.db.models.profile import (
    PreferenceRecord,
    ProfileVersionRecord,
    SkillRecord,
)
from app.db.models.profile import Profile as ProfileRecord
from app.domain.job_filters.entities import JobFilterRules
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.infrastructure.linkedin_mcp.notification_state import NotificationStateRepository
from app.infrastructure.telegram.notification import TelegramNotificationService
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.linkedin_mcp_pipeline_service import LinkedInMCPPipelineService
from app.services.linkedin_notify_service import LinkedInNotifyService
from app.services.user_filter_service import (
    UserFilterService,
    load_job_filter_rules,
    save_job_filter_rules,
)
from app.shared.time import utc_now
from sqlalchemy import func, select
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


def _add_linkedin_source(session: Session) -> JobSource:
    """Create an active LinkedIn MCP source pointing at the stub server."""
    source = JobSource(
        name="LinkedIn Stub",
        type=JobSourceType.LINKEDIN_MCP.value,
        base_url=sys.executable,
        config_json={
            "search_tool": "search_jobs",
            "detail_tool": "get_job_details",
            "server_command": sys.executable,
            "server_args": [str(_STUB_SERVER)],
            "server_cwd": str(_REPO_ROOT),
        },
        is_active=True,
    )
    session.add(source)
    session.commit()
    return source


def _set_rules(session: Session, rules: JobFilterRules) -> None:
    save_job_filter_rules(session, rules)


def test_pipeline_empty_rules_filter_nothing(db_session: Session) -> None:
    """An empty user filter config is a clean pass-through (zero filtered)."""
    _add_profile(db_session)
    _add_linkedin_source(db_session)
    _set_rules(db_session, JobFilterRules())

    result = LinkedInMCPPipelineService(session=db_session).run()

    assert result.fetched >= 1
    assert result.filtered == 0
    assert result.matched_total >= 1
    assert result.filter_rejection_breakdown == {}
    assert result.inserted == result.matched_total


def test_pipeline_excluded_company_filters_and_reports_breakdown(
    db_session: Session,
) -> None:
    """Filtering by excluded company drops the fetched job and reports the breakdown."""
    _add_profile(db_session)
    _add_linkedin_source(db_session)
    _set_rules(db_session, JobFilterRules(excluded_companies=["acme tech"]))

    result = LinkedInMCPPipelineService(session=db_session).run()

    assert result.fetched >= 1
    assert result.inserted == 1
    assert result.filtered == 1
    assert result.filter_rejection_breakdown == {"excluded_company": 1}
    assert result.matched_total == 0
    assert result.recommendations == ()
    # The filtered job never reached the matching stage.
    assert db_session.scalar(select(func.count()).select_from(JobMatch)) == 0


def test_pipeline_filtering_everything_stops_matching(db_session: Session) -> None:
    """When every inserted job is filtered, nothing is matched or delivered."""
    _add_profile(db_session)
    _add_linkedin_source(db_session)
    _set_rules(db_session, JobFilterRules(required_locations=["nowhere"]))

    result = LinkedInMCPPipelineService(session=db_session).run()

    assert result.fetched >= 1
    assert result.filtered == result.inserted
    assert result.matched_total == 0
    assert result.recommendations == ()
    # Filtered jobs never reached the matching stage: no JobMatch records exist.
    assert db_session.scalar(select(func.count()).select_from(JobMatch)) == 0


def test_discovery_summary_reports_filter_metrics(db_session: Session) -> None:
    """Discovery summary exposes filtered count, ids, and breakdown."""
    source = JobSourceConfig(
        id=1,
        name="Fake Feed",
        type=JobSourceType.RSS_FEED,
        base_url="https://example.com/rss.xml",
        config={},
    )
    registry = ConnectorRegistry([_FakeConnector()])
    service = DiscoveryService(
        session=db_session,
        connector_registry=registry,
        normalizer=JobNormalizationService(),
        matching_service=JobMatchingService(
            db_session,
            HardFilterService(FilterRules()),
            DuplicateDetectionService(db_session),
        ),
        user_filter_service=UserFilterService(
            db_session, rules=JobFilterRules(excluded_companies=["acme tech"])
        ),
    )

    summary = service.run_source(source)

    assert summary.inserted_count == 1
    assert summary.filtered_count == 1
    assert len(summary.filtered_job_ids) == 1
    assert summary.filter_rejection_breakdown == {"excluded_company": 1}
    # The filtered job is a subset of the inserted set (it was persisted), but
    # the pipeline must never hand it to matching.
    assert set(summary.filtered_job_ids).issubset(summary.inserted_job_ids)
    # The filtered job never reached the matching stage.
    assert db_session.scalar(select(func.count()).select_from(JobMatch)) == 0


class _FakeConnector:
    """Fake source connector returning one job that the filter excludes."""

    source_type = JobSourceType.RSS_FEED

    def fetch(self, _source: object) -> list[DiscoveredJob]:
        return [
            DiscoveredJob(
                external_id="job-1",
                url="https://example.com/jobs/1",
                title="Software Internship",
                company="Acme Tech",
                location="Remote",
                description="Build APIs",
                raw_payload={"id": "job-1"},
                discovered_at=utc_now(),
            )
        ]


def _seed_historical_mock_job(session: Session, source: JobSource, *, tag: str, title: str) -> None:
    """Insert a stored job shaped like the leaked MOCK-101/MOCK-102 records."""
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


class _FakeNotifier(TelegramNotificationService):
    """Notifier that records match URLs instead of reaching out to Telegram."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_linkedin_matches(self, recommendations: object) -> int:
        matches = [rec for rec in recommendations if rec.above_threshold]  # type: ignore[union-attr]
        self.sent = [rec.url for rec in matches]
        return len(self.sent)


class _InMemoryState(NotificationStateRepository):
    """In-memory notification state repo for dedup tests."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_notified(self, url: str) -> bool:
        return url in self._seen

    def mark_notified(self, url: str) -> None:
        self._seen.add(url)


def test_notify_with_active_filter_never_delivers_stored_mock_jobs(
    db_session: Session,
) -> None:
    """Active filters never cause fallback to, or delivery of, stored mocks."""
    _add_profile(db_session)
    source = _add_linkedin_source(db_session)
    _seed_historical_mock_job(db_session, source, tag="101", title="Stored Mock PFE")
    _seed_historical_mock_job(db_session, source, tag="102", title="Stored Mock Apprenticeship")
    # A filter that excludes every job of the current fetch.
    _set_rules(db_session, JobFilterRules(required_locations=["nowhere"]))

    notifier = _FakeNotifier()
    result = LinkedInNotifyService(
        session=db_session, state_repo=_InMemoryState(), notifier=notifier
    ).run()

    assert result.status == "ok"
    assert result.filtered >= 1
    assert result.matched_total == 0
    assert result.telegram_sent == 0
    assert notifier.sent == []
    assert not any("mock-" in url for url in notifier.sent)


def test_rules_persist_and_reload(db_session: Session) -> None:
    """Saved rules round-trip through the singleton DB row."""
    _set_rules(db_session, JobFilterRules(required_titles=["engineer"], remote_only=True))
    loaded = load_job_filter_rules(db_session)
    assert loaded.required_titles == ["engineer"]
    assert loaded.remote_only is True
