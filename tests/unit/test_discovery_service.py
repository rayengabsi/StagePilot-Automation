from __future__ import annotations

from app.config.settings import FilterRules
from app.db.base import Base
from app.db.models.discovery import DiscoveryMetricRecord
from app.db.models.jobs import Job, JobSource, RawJob
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.shared.time import utc_now
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker


class _FakeConnector:
    """Fake source connector for discovery service tests."""

    source_type = JobSourceType.RSS_FEED

    def fetch(self, _source: JobSourceConfig) -> list[DiscoveredJob]:
        """Return one stable discovered job."""
        return [
            DiscoveredJob(
                external_id="job-1",
                url="https://example.com/jobs/1",
                title="Software Internship",
                company="Example",
                location="Remote",
                description="Build APIs",
                raw_payload={"id": "job-1"},
                discovered_at=utc_now(),
            )
        ]


def _build_matching_service(session: Session) -> JobMatchingService:
    """Build a JobMatchingService with default rules for testing."""
    filters = HardFilterService(FilterRules())
    duplicates = DuplicateDetectionService(session)
    return JobMatchingService(session, filters, duplicates)


def test_discovery_service_ingests_and_skips_duplicate_jobs() -> None:
    """Discovery should insert new jobs and skip duplicates on later runs."""
    session = _create_session()
    session.add(
        JobSource(
            name="Example",
            type=JobSourceType.RSS_FEED.value,
            base_url="https://example.com/rss.xml",
            config_json={},
            is_active=True,
        )
    )
    session.commit()
    service = DiscoveryService(
        session=session,
        connector_registry=ConnectorRegistry([_FakeConnector()]),
        normalizer=JobNormalizationService(),
        matching_service=_build_matching_service(session),
    )

    first = service.run_once()
    second = service.run_once()

    assert first.inserted_count == 1
    assert first.duplicate_count == 0
    assert first.accepted >= 1
    assert second.inserted_count == 0
    assert second.duplicate_count == 1
    assert session.scalar(select(func.count()).select_from(Job)) == 1
    assert session.scalar(select(func.count()).select_from(RawJob)) == 1


def test_discovery_records_per_source_metrics() -> None:
    """Each discovery run should persist a metric record per source."""
    session = _create_session()
    session.add(
        JobSource(
            name="Example",
            type=JobSourceType.RSS_FEED.value,
            base_url="https://example.com/rss.xml",
            config_json={},
            is_active=True,
        )
    )
    session.commit()
    service = DiscoveryService(
        session=session,
        connector_registry=ConnectorRegistry([_FakeConnector()]),
        normalizer=JobNormalizationService(),
        matching_service=_build_matching_service(session),
    )

    service.run_once()

    metrics = session.scalars(select(DiscoveryMetricRecord)).all()
    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.provider == "rss_feed"
    assert metric.jobs_fetched == 1
    assert metric.jobs_inserted == 1
    assert metric.status == "ok"


def test_discovery_reports_rejection_metrics() -> None:
    """Discovery summary should include rejection breakdown for filtered jobs."""
    session = _create_session()
    session.add(
        JobSource(
            name="Example",
            type=JobSourceType.RSS_FEED.value,
            base_url="https://example.com/rss.xml",
            config_json={},
            is_active=True,
        )
    )
    session.commit()

    class _RejectedFakeConnector:
        """Returns a job that will be rejected by hard filters."""

        source_type = JobSourceType.RSS_FEED

        def fetch(self, _source: JobSourceConfig) -> list[DiscoveredJob]:
            return [
                DiscoveredJob(
                    external_id="job-senior",
                    url="https://example.com/jobs/senior",
                    title="Senior Lead Manager CDI",
                    company="Example",
                    location="USA",
                    description="Full-time permanent director-level role.",
                    raw_payload={"id": "job-senior"},
                    discovered_at=utc_now(),
                )
            ]

    service = DiscoveryService(
        session=session,
        connector_registry=ConnectorRegistry([_RejectedFakeConnector()]),
        normalizer=JobNormalizationService(),
        matching_service=_build_matching_service(session),
    )

    summary = service.run_once()
    assert summary.inserted_count == 1
    assert summary.accepted == 0
    assert summary.rejected >= 1
    assert len(summary.rejection_breakdown) >= 2


def _create_session() -> Session:
    """Create an isolated in-memory SQLAlchemy session."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()
