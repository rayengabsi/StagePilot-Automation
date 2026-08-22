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


class _MixedQualityConnector:
    """Returns a mix of valid and malformed jobs to test isolation."""

    source_type = JobSourceType.RSS_FEED

    def fetch(self, _source: JobSourceConfig) -> list[DiscoveredJob]:
        return [
            DiscoveredJob(
                external_id="job-valid-1",
                url="https://example.com/jobs/valid-1",
                title="Software Internship",
                company="GoodCorp",
                location="Remote",
                description="Build APIs",
                raw_payload={"id": "job-valid-1"},
                discovered_at=utc_now(),
            ),
            DiscoveredJob(
                external_id="job-malformed",
                url="https://example.com/jobs/malformed",
                title="Staff Engineer",
                company="BadDataCorp",
                location="x" * 500,
                description="Oversized location field",
                raw_payload={"id": "job-malformed"},
                discovered_at=utc_now(),
            ),
            DiscoveredJob(
                external_id="job-valid-2",
                url="https://example.com/jobs/valid-2",
                title="Data Analyst",
                company="AnotherCorp",
                location="New York",
                description="Analyze data",
                raw_payload={"id": "job-valid-2"},
                discovered_at=utc_now(),
            ),
        ]


def test_malformed_job_does_not_abort_discovery() -> None:
    """One oversized field must be rejected while other valid jobs are still inserted."""
    session = _create_session()
    session.add(
        JobSource(
            name="MixedSource",
            type=JobSourceType.RSS_FEED.value,
            base_url="https://example.com/rss.xml",
            config_json={},
            is_active=True,
        )
    )
    session.commit()
    service = DiscoveryService(
        session=session,
        connector_registry=ConnectorRegistry([_MixedQualityConnector()]),
        normalizer=JobNormalizationService(),
        matching_service=_build_matching_service(session),
    )

    summary = service.run_once()

    assert summary.fetched_count == 3
    assert summary.inserted_count == 2
    assert summary.invalid_count == 1
    assert summary.failed_sources_count == 0
    assert session.scalar(select(func.count()).select_from(Job)) == 2


def test_source_not_marked_failed_for_invalid_job() -> None:
    """A single invalid job should not cause the source to be marked as failed."""
    session = _create_session()
    session.add(
        JobSource(
            name="MixedSource",
            type=JobSourceType.RSS_FEED.value,
            base_url="https://example.com/rss.xml",
            config_json={},
            is_active=True,
        )
    )
    session.commit()
    service = DiscoveryService(
        session=session,
        connector_registry=ConnectorRegistry([_MixedQualityConnector()]),
        normalizer=JobNormalizationService(),
        matching_service=_build_matching_service(session),
    )

    summary = service.run_once()

    metrics = session.scalars(select(DiscoveryMetricRecord)).all()
    assert len(metrics) == 1
    assert metrics[0].status == "ok"
    assert metrics[0].invalid == 1
    assert len(summary.source_errors) == 0


def test_session_usable_after_malformed_job() -> None:
    """The DB session must remain usable after rejecting a malformed job."""
    session = _create_session()
    session.add(
        JobSource(
            name="MixedSource",
            type=JobSourceType.RSS_FEED.value,
            base_url="https://example.com/rss.xml",
            config_json={},
            is_active=True,
        )
    )
    session.commit()
    service = DiscoveryService(
        session=session,
        connector_registry=ConnectorRegistry([_MixedQualityConnector()]),
        normalizer=JobNormalizationService(),
        matching_service=_build_matching_service(session),
    )

    first = service.run_once()
    second = service.run_once()

    assert first.invalid_count == 1
    assert first.inserted_count == 2
    assert second.duplicate_count == 2
    assert second.inserted_count == 0
    assert session.scalar(select(func.count()).select_from(Job)) == 2


def test_oversized_location_not_committed_to_db() -> None:
    """A job with an oversized location must not be persisted at all."""
    session = _create_session()
    session.add(
        JobSource(
            name="MixedSource",
            type=JobSourceType.RSS_FEED.value,
            base_url="https://example.com/rss.xml",
            config_json={},
            is_active=True,
        )
    )
    session.commit()
    service = DiscoveryService(
        session=session,
        connector_registry=ConnectorRegistry([_MixedQualityConnector()]),
        normalizer=JobNormalizationService(),
        matching_service=_build_matching_service(session),
    )

    service.run_once()

    jobs = session.scalars(select(Job)).all()
    locations = [j.location for j in jobs]
    assert all(loc is None or len(loc) <= 255 for loc in locations)


def _create_session() -> Session:
    """Create an isolated in-memory SQLAlchemy session."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_discovery_metrics_error_column_supports_long_text() -> None:
    """The error column must support long exceptions (>500 chars)."""
    session = _create_session()
    long_error_msg = "X" * 2000

    metric = DiscoveryMetricRecord(
        run_id="test-run", provider="test", status="failed", error=long_error_msg
    )
    session.add(metric)
    session.commit()

    fetched = session.scalar(
        select(DiscoveryMetricRecord).where(DiscoveryMetricRecord.run_id == "test-run")
    )
    assert fetched is not None
    assert fetched.error == long_error_msg
    assert len(fetched.error) == 2000
