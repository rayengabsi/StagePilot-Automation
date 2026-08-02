"""Integration tests for provider validation and error isolation."""

from __future__ import annotations

from app.config.settings import Settings
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceFetchError
from app.infrastructure.job_sources.registry import ConnectorRegistry, build_connector_registry
from app.infrastructure.job_sources.validation import ConnectorValidator
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.source_validation_service import SourceValidationService
from app.shared.time import utc_now
from sqlalchemy.orm import Session


def _source(
    source_type: JobSourceType,
    base_url: str,
    config: dict[str, object] | None = None,
    source_id: int = 1,
) -> JobSourceConfig:
    """Build a job source config helper."""
    return JobSourceConfig(
        id=source_id,
        name="Test Source",
        type=source_type,
        base_url=base_url,
        config=config or {},
    )


def _service(session: Session, registry: ConnectorRegistry) -> DiscoveryService:
    """Build a DiscoveryService over the given registry."""
    return DiscoveryService(
        session=session,
        connector_registry=registry,
        normalizer=JobNormalizationService(),
        matching_service=JobMatchingService(
            session,
            HardFilterService(Settings().filter_rules),
            DuplicateDetectionService(session),
        ),
    )


class _FailingConnector:
    """Connector test double that always raises on fetch."""

    source_type = JobSourceType.LEVER

    def fetch(self, _source: JobSourceConfig) -> list[DiscoveredJob]:
        """Raise a transport error for every source."""
        raise SourceFetchError("simulated outage")


class _HealthyConnector:
    """Connector test double that returns one fixed job."""

    source_type = JobSourceType.GREENHOUSE

    def fetch(self, _source: JobSourceConfig) -> list[DiscoveredJob]:
        """Return one stable discovered job."""
        return [
            DiscoveredJob(
                external_id="g-1",
                url="https://boards.greenhouse.io/acme/jobs/1",
                title="Backend Engineer",
                company="Acme",
                location="Paris, France",
                description="Build APIs",
                raw_payload={"id": "g-1"},
                discovered_at=utc_now(),
            )
        ]


def test_one_failing_source_does_not_interrupt_others(db_session: Session) -> None:
    """A provider outage should be isolated to that source."""
    from app.db.models.discovery import DiscoveryMetricRecord
    from app.db.models.jobs import Job, JobSource
    from sqlalchemy import func, select

    db_session.add_all(
        [
            JobSource(
                name="Greenhouse Acme",
                type=JobSourceType.GREENHOUSE.value,
                base_url="https://boards.greenhouse.io/acme",
                config_json={"token": "acme"},
                is_active=True,
            ),
            JobSource(
                name="Lever Acme",
                type=JobSourceType.LEVER.value,
                base_url="https://jobs.lever.co/acme",
                config_json={"company": "acme"},
                is_active=True,
            ),
        ]
    )
    db_session.commit()

    registry = ConnectorRegistry([_HealthyConnector(), _FailingConnector()])
    summary = _service(db_session, registry).run_once()

    assert summary.sources_count == 2
    assert summary.failed_sources_count == 1
    assert summary.fetched_count == 1
    assert summary.inserted_count == 1
    assert db_session.scalar(select(func.count()).select_from(Job)) == 1

    metrics = db_session.scalars(select(DiscoveryMetricRecord)).all()
    assert len(metrics) == 2
    statuses = {metric.provider: metric.status for metric in metrics}
    assert statuses["greenhouse"] == "ok"
    assert statuses["lever"] == "failed"
    failed = next(metric for metric in metrics if metric.provider == "lever")
    assert "simulated outage" in failed.error


def test_benchmark_invalid_source_fails_only_that_source() -> None:
    """A malformed config should fail its own report entry only."""
    registry = build_connector_registry(Settings())
    service = SourceValidationService(settings=Settings(), registry=registry)
    good = _source(
        JobSourceType.GREENHOUSE,
        "https://boards.greenhouse.io/acme",
        {"token": "acme", "company": "Acme"},
        source_id=1,
    )
    bad = _source(
        JobSourceType.GREENHOUSE,
        "https://boards.greenhouse.io",
        {},
        source_id=2,
    )

    report = service.benchmark_sources([good, bad])

    assert report.sources_count == 2
    assert report.failed_count == 1
    assert report.healthy_count == 1
    by_id = {entry.source_id: entry for entry in report.sources}
    assert by_id[1].status == "healthy"
    assert by_id[2].status == "failed"
    assert any("source config invalid" in issue for issue in by_id[2].issues)


def test_benchmark_with_no_sources_covers_all_providers() -> None:
    """Without sources the report should cover every registered provider."""
    service = SourceValidationService(settings=Settings())
    report = service.benchmark_sources([])

    registry = build_connector_registry(Settings())
    assert report.sources_count == len(registry.all())
    assert report.healthy_count == len(registry.all())
    assert report.overall_status == "healthy"
    assert {entry.provider for entry in report.sources} == {
        connector.provider_name for connector in registry.all()
    }


def test_connector_validator_uses_mocked_http_only() -> None:
    """Validating a connector never performs network requests."""
    registry = build_connector_registry(Settings())
    validator = ConnectorValidator(Settings())

    for connector in registry.all():
        result = validator.validate_connector(connector)
        assert result.status == "healthy"
