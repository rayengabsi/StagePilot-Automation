"""Integration tests for the Recommendation Intelligence Layer.

Proves enriched recommendations (weighted breakdown, confidence, reasoning)
flow correctly from discovery through recommendation, persistence, and into
the approval/Telegram surface.
"""

from __future__ import annotations

from app.config.matching import MatchingConfig
from app.config.settings import FilterRules
from app.db.models.jobs import Job, JobSource
from app.db.models.profile import (
    PreferenceRecord,
    ProfileVersionRecord,
    SkillRecord,
)
from app.db.models.profile import (
    Profile as ProfileRecord,
)
from app.db.models.recommendation import RecommendationRecord
from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.package import build_snapshot, create_application_package
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.recommendation.enums import ConfidenceLevel, RecommendationStatus
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.infrastructure.telegram.messages import format_application_message
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.recommendation_service import RecommendationService
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
) -> DiscoveredJob:
    """Build a discovered remote job helper."""
    return DiscoveredJob(
        external_id=external_id,
        url=f"https://acme.com/{external_id}",
        title=title,
        company="Acme",
        location="Remote",
        description=description,
        remote_status="remote",
        raw_payload={"id": external_id},
        discovered_at=utc_now(),
    )


def _discovery_service(session: Session, registry: ConnectorRegistry) -> DiscoveryService:
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


def _intelligence_config() -> MatchingConfig:
    """Matching config with the intelligence weights and no hard rules."""
    return MatchingConfig(
        weights={
            "skills": 35.0,
            "technologies": 20.0,
            "education": 10.0,
            "experience": 10.0,
            "languages": 5.0,
            "projects": 5.0,
            "location": 10.0,
            "preferences": 5.0,
            "classification": 15.0,
            "remote": 5.0,
            "seniority": 5.0,
            "hard_filters": 10.0,
            "ai": 0.0,
        },
        thresholds={"recommendation_cutoff": 0.0},
        hard_rules={},
        fuzz_threshold=60,
    )


def _add_source(session: Session) -> JobSource:
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


def _add_profile(session: Session) -> ProfileRecord:
    """Create an active profile with Python/FastAPI skills and remote preference."""
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
    session.add(SkillRecord(profile_id=profile.id, name="FastAPI"))
    session.add(PreferenceRecord(profile_id=profile.id, remote_preference="remote"))
    session.commit()
    return profile


def _run_discovery(session: Session) -> None:
    _add_source(session)
    registry = ConnectorRegistry(
        [
            _StaticConnector(
                JobSourceType.GREENHOUSE,
                [
                    _discovered(
                        "j1",
                        "Backend Engineer",
                        "Build Python and FastAPI microservices.",
                    ),
                    _discovered(
                        "j2",
                        "Frontend Developer",
                        "Build React and TypeScript interfaces.",
                    ),
                    _discovered(
                        "j3",
                        "Data Engineer",
                        "Build Spark and Airflow pipelines in Python.",
                    ),
                ],
            ),
        ]
    )
    _discovery_service(session, registry).run_once()


def test_recommendations_carry_weighted_breakdown_and_insights(db_session: Session) -> None:
    """Enriched recommendations expose weighted components and insights."""
    _run_discovery(db_session)
    _add_profile(db_session)

    recommendations = RecommendationService(
        session=db_session, config=_intelligence_config()
    ).recommend()

    assert len(recommendations) == 3

    top = recommendations[0]
    assert top.final_score > recommendations[1].final_score > recommendations[2].final_score
    assert top.weighted_breakdown is not None
    assert top.weighted_breakdown.final_score == top.final_score
    assert top.weighted_breakdown.component("skills") is not None
    assert top.weighted_breakdown.component("classification") is not None
    assert top.weighted_breakdown.component("remote") is not None
    assert top.weighted_breakdown.component("seniority") is not None
    assert top.weighted_breakdown.component("hard_filters") is not None

    assert top.insights is not None
    assert top.insights.confidence == ConfidenceLevel.VERY_HIGH
    assert recommendations[1].insights.confidence == ConfidenceLevel.MEDIUM
    assert recommendations[2].insights.confidence == ConfidenceLevel.LOW
    assert any("Strong FastAPI and Python match" in r for r in top.insights.reasons)
    assert any("Location mismatch" in r for r in top.insights.reasons)
    assert any("Remote-friendly role" in r for r in top.insights.reasons)
    assert top.insights.summary


def test_recommendations_persist_and_round_trip(db_session: Session) -> None:
    """Weighted breakdown and insights survive persistence and reload."""
    _run_discovery(db_session)
    _add_profile(db_session)
    service = RecommendationService(session=db_session, config=_intelligence_config())

    service.recommend()

    records = db_session.scalars(select(RecommendationRecord)).all()
    assert len(records) == 3
    for record in records:
        assert record.weighted_breakdown_json is not None
        assert "final_score" in record.weighted_breakdown_json
        assert record.insights_json is not None
        assert "confidence" in record.insights_json
        assert "reasons" in record.insights_json

    reloaded = service.list_recommendations()
    assert len(reloaded) == 3
    for rec in reloaded:
        assert rec.weighted_breakdown is not None
        assert rec.insights is not None
        assert rec.insights.confidence in set(ConfidenceLevel)
        assert rec.to_dict()["insights"]["confidence"] == rec.insights.confidence.value


def test_enriched_recommendation_flows_to_approval_telegram(db_session: Session) -> None:
    """The enriched recommendation appears in the approval snapshot and Telegram message."""
    _run_discovery(db_session)
    _add_profile(db_session)
    recommendations = RecommendationService(
        session=db_session, config=_intelligence_config()
    ).recommend()
    top = recommendations[0]

    job = db_session.scalar(select(Job).where(Job.external_id == "j1"))
    assert job is not None

    recommendation_data = {
        "job": {
            "id": top.job_id,
            "title": job.title,
            "company": job.company or "",
            "location": job.location or "",
            "description_preview": (job.description or "")[:500],
        },
        "final_score": top.final_score,
        "matched_skills": list(top.matched_detail.matched_skills),
        "missing_skills": list(top.matched_detail.missing_skills),
        "score_breakdown": top.score_breakdown.to_dict(),
        "weighted_breakdown": top.weighted_breakdown.to_dict(),
        "insights": top.insights.to_dict(),
    }
    snapshot_json = build_snapshot(
        recommendation_data=recommendation_data,
        profile_data={"name": "Test User"},
        explanation="AI explanation here",
        tailored_resume=None,
        cover_letter_body="body",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="modern",
        theme_name="default",
    )
    package = create_application_package(
        recommendation_id=top.job_id,
        job_id=top.job_id,
        profile_id=top.profile_id,
        final_score=top.final_score,
        snapshot_json=snapshot_json,
        documents_json="{}",
    )

    assert package.status.value == "new"
    assert isinstance(package, ApplicationPackage)

    message = format_application_message(package)
    assert "🧭 *Confidence:* `Very High`" in message
    assert "✨ *Why This Matches You*" in message
    assert top.insights.summary in message
    assert top.status in (RecommendationStatus.ACTIVE, RecommendationStatus.REJECTED)
