"""Integration tests for the Job Intelligence enrichment pipeline."""

from __future__ import annotations

from app.config.matching import MatchingConfig
from app.config.settings import FilterRules
from app.db.models.jobs import Job, JobSource
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.master_profile.entities import MasterProfile, PersonalInfo, Preference, Skill
from app.domain.recommendation.scorer import SimilarityScorer
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.shared.time import utc_now
from sqlalchemy import select
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
    title: str,
    description: str,
    location: str | None = None,
    remote_status: str | None = None,
) -> DiscoveredJob:
    """Build a discovered job helper."""
    return DiscoveredJob(
        external_id=external_id,
        url=f"https://acme.com/{external_id}",
        title=title,
        company="Acme",
        location=location,
        description=description,
        raw_payload={"id": external_id},
        discovered_at=utc_now(),
        remote_status=remote_status,
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


def _add_source(session: Session) -> JobSource:
    """Create and return an active source row."""
    source = JobSource(
        name="Acme Board",
        type=JobSourceType.GREENHOUSE.value,
        base_url="https://boards.greenhouse.io/acme",
        config_json={"token": "acme"},
        is_active=True,
    )
    session.add(source)
    session.commit()
    return source


def test_discovery_persists_classification_columns(db_session: Session) -> None:
    """Enrichment should flow into persisted classification columns."""
    _add_source(db_session)
    registry = ConnectorRegistry(
        [
            _StaticConnector(
                JobSourceType.GREENHOUSE,
                [
                    _discovered(
                        "b1",
                        "Senior Backend Engineer",
                        "Build and operate distributed microservices.",
                        location="Remote",
                        remote_status="remote",
                    ),
                    _discovered(
                        "f1",
                        "Internship — Frontend Developer",
                        "React and TypeScript, full-time on-site.",
                    ),
                ],
            ),
        ]
    )

    summary = _service(db_session, registry).run_once()

    assert summary.inserted_count == 2

    backend = db_session.scalar(select(Job).where(Job.external_id == "b1"))
    assert backend is not None
    assert backend.classification_specialization == "backend"
    assert backend.classification_seniority == "senior"
    assert backend.classification_work_mode == "remote"

    frontend = db_session.scalar(select(Job).where(Job.external_id == "f1"))
    assert frontend is not None
    assert frontend.classification_specialization == "frontend"
    assert frontend.classification_seniority == "intern"
    assert frontend.classification_employment_type == "internship"
    assert frontend.classification_work_mode == "onsite"

    # Original extracted values are preserved alongside the normalized labels.
    assert backend.remote_status == "remote"
    assert backend.classification_work_mode == "remote"


def test_original_fields_preserved_with_classification(db_session: Session) -> None:
    """Original metadata should not be overwritten by classification."""
    _add_source(db_session)
    registry = ConnectorRegistry(
        [
            _StaticConnector(
                JobSourceType.GREENHOUSE,
                [
                    _discovered(
                        "g1",
                        "Software Engineer",
                        "Full-time engineering role.",
                    ),
                ],
            ),
        ]
    )

    _service(db_session, registry).run_once()

    job = db_session.scalar(select(Job).where(Job.external_id == "g1"))
    assert job is not None
    assert job.classification_employment_type == "full_time"
    assert job.employment_type is None


def test_classification_boosts_recommendation_scoring(db_session: Session) -> None:
    """Enriched specialization should contribute to skills matching."""
    _add_source(db_session)
    registry = ConnectorRegistry(
        [
            _StaticConnector(
                JobSourceType.GREENHOUSE,
                [
                    _discovered("r1", "Backend Engineer", "Distributed systems role."),
                    _discovered("r2", "Software Engineer", "General engineering role."),
                ],
            ),
        ]
    )

    _service(db_session, registry).run_once()

    backend_job = db_session.scalar(select(Job).where(Job.external_id == "r1"))
    generic_job = db_session.scalar(select(Job).where(Job.external_id == "r2"))
    assert backend_job is not None and generic_job is not None
    assert backend_job.classification_specialization == "backend"
    assert generic_job.classification_specialization is None

    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="Test"),
        skills=(Skill(name="backend"),),
        experience=(),
        education=(),
        languages=(),
        projects=(),
        preferences=Preference(),
    )
    scorer = SimilarityScorer(
        MatchingConfig(weights={}, thresholds={}, hard_rules={}, fuzz_threshold=60)
    )

    enriched = scorer.match_detail(profile, backend_job)
    unenriched = scorer.match_detail(profile, generic_job)

    assert "backend" in enriched.matched_skills
    assert "backend" not in unenriched.matched_skills
