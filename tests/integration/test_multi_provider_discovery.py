"""Integration tests for multi-provider job discovery."""

from __future__ import annotations

from app.config.settings import FilterRules
from app.db.models.discovery import DiscoveryMetricRecord
from app.db.models.jobs import Job, JobSource
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.shared.time import utc_now
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class _StaticConnector:
    """Connector test double that returns a fixed set of jobs."""

    def __init__(self, source_type: JobSourceType, jobs: list[DiscoveredJob]) -> None:
        """Initialize with the source type and jobs to return."""
        self.source_type = source_type
        self._jobs = jobs

    def fetch(self, _source: JobSourceConfig) -> list[DiscoveredJob]:
        """Return the configured jobs."""
        return self._jobs


def _discovered(
    external_id: str,
    url: str,
    title: str,
    company: str,
) -> DiscoveredJob:
    """Build a discovered job helper."""
    return DiscoveredJob(
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        location="Remote",
        description="Python and SQL",
        raw_payload={"id": external_id},
        discovered_at=utc_now(),
    )


def _service(session: Session, registry: ConnectorRegistry) -> DiscoveryService:
    """Build a DiscoveryService over the given registry."""
    return DiscoveryService(
        session=session,
        connector_registry=registry,
        normalizer=JobNormalizationService(),
        matching_service=JobMatchingService(
            session,
            HardFilterService(FilterRules()),
            DuplicateDetectionService(session),
        ),
    )


def test_discovery_ingests_from_multiple_providers(db_session: Session) -> None:
    """Jobs from different providers should be ingested in one run."""
    greenhouse = JobSource(
        name="Greenhouse Acme",
        type=JobSourceType.GREENHOUSE.value,
        base_url="https://boards.greenhouse.io/acme",
        config_json={"token": "acme"},
        is_active=True,
    )
    lever = JobSource(
        name="Lever Acme",
        type=JobSourceType.LEVER.value,
        base_url="https://jobs.lever.co/acme",
        config_json={"company": "acme"},
        is_active=True,
    )
    db_session.add_all([greenhouse, lever])
    db_session.commit()

    registry = ConnectorRegistry(
        [
            _StaticConnector(
                JobSourceType.GREENHOUSE,
                [_discovered("g1", "https://acme.com/g1", "Engineer", "Acme")],
            ),
            _StaticConnector(
                JobSourceType.LEVER,
                [
                    _discovered("l1", "https://acme.com/l1", "Designer", "Acme"),
                    _discovered("l2", "https://acme.com/l2", "Marketer", "Acme"),
                ],
            ),
        ]
    )

    summary = _service(db_session, registry).run_once()

    assert summary.sources_count == 2
    assert summary.fetched_count == 3
    assert summary.inserted_count == 3
    assert db_session.scalar(select(func.count()).select_from(Job)) == 3

    metrics = db_session.scalars(select(DiscoveryMetricRecord)).all()
    assert len(metrics) == 2
    assert {metric.provider for metric in metrics} == {"greenhouse", "lever"}


def test_discovery_dedupes_across_providers(db_session: Session) -> None:
    """The same job posted by two providers should be ingested once."""
    greenhouse = JobSource(
        name="Greenhouse Dupe",
        type=JobSourceType.GREENHOUSE.value,
        base_url="https://boards.greenhouse.io/acme",
        config_json={"token": "acme"},
        is_active=True,
    )
    db_session.add(greenhouse)
    db_session.commit()
    # A second source that mirrors the same posting URL.
    lever = JobSource(
        name="Lever Dupe",
        type=JobSourceType.LEVER.value,
        base_url="https://jobs.lever.co/acme",
        config_json={"company": "acme"},
        is_active=True,
    )
    db_session.add(lever)
    db_session.commit()

    registry = ConnectorRegistry(
        [
            _StaticConnector(
                JobSourceType.GREENHOUSE,
                [_discovered("g1", "https://acme.com/job", "Engineer", "Acme")],
            ),
            _StaticConnector(
                JobSourceType.LEVER,
                [_discovered("l1", "https://acme.com/job", "Engineer", "Acme")],
            ),
        ]
    )

    summary = _service(db_session, registry).run_once()

    assert summary.inserted_count == 1
    assert summary.duplicate_count == 1
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1
