from __future__ import annotations

from app.db.base import Base
from app.db.models.jobs import Job, JobSource, RawJob
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.services.discovery_service import DiscoveryService
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
    )

    first = service.run_once()
    second = service.run_once()

    assert first.inserted_count == 1
    assert first.duplicate_count == 0
    assert second.inserted_count == 0
    assert second.duplicate_count == 1
    assert session.scalar(select(func.count()).select_from(Job)) == 1
    assert session.scalar(select(func.count()).select_from(RawJob)) == 1


def _create_session() -> Session:
    """Create an isolated in-memory SQLAlchemy session."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()
