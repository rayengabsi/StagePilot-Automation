"""Milestone 2: feed LinkedIn MCP jobs into the existing matching pipeline.

This service is a thin adapter only. It:
  1. loads the active LinkedIn MCP source from the database,
  2. builds a connector registry that always includes the LinkedIn MCP
     connector (LinkedIn is opt-in in ``providers.toml``),
  3. runs the existing ``DiscoveryService`` (normalize → classify → ingest →
     hard-filter → JobMatch),
  4. runs the existing ``RecommendationService`` to compute deterministic,
     explainable match scores, and
  5. filters results by the configured ``recommendation_cutoff`` threshold.

No matching algorithm is modified. Explanations are generated deterministically
from the explainable scoring artifacts (matched/missing skills, score breakdown,
insights); an ``explainer`` callable can be injected to override this.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.matching import get_matching_config
from app.config.settings import Settings, get_settings
from app.db.models.jobs import Job, JobSource
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.domain.recommendation.entities import Recommendation
from app.infrastructure.job_sources.linkedin_mcp_connector import LinkedInMCPConnector
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.recommendation_service import RecommendationService

Explainer = Callable[[Recommendation, str, str], str]


@dataclass(frozen=True, slots=True)
class LinkedInMCPRecommendationResult:
    """One threshold-filtered recommendation with its explanation."""

    job_id: int
    title: str
    company: str | None
    url: str
    final_score: float
    status: str
    above_threshold: bool
    explanation: str
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "url": self.url,
            "final_score": round(self.final_score, 2),
            "status": self.status,
            "above_threshold": self.above_threshold,
            "explanation": self.explanation,
            "matched_skills": list(self.matched_skills),
            "missing_skills": list(self.missing_skills),
        }


@dataclass(frozen=True, slots=True)
class LinkedInMCPPipelineResult:
    """Outcome of one LinkedIn MCP matching run."""

    source_id: int
    source_name: str
    cutoff: float
    fetched: int
    inserted: int
    duplicates: int
    rejected: int
    matched_total: int
    above_threshold: int
    below_threshold: int
    recommendations: tuple[LinkedInMCPRecommendationResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "threshold": self.cutoff,
            "fetched": self.fetched,
            "inserted": self.inserted,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "matched_total": self.matched_total,
            "above_threshold": self.above_threshold,
            "below_threshold": self.below_threshold,
            "recommendations": [rec.to_dict() for rec in self.recommendations],
        }


class LinkedInMCPPipelineService:
    """Run the LinkedIn MCP → matching pipeline end to end."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        explainer: Explainer | None = None,
        cutoff: float | None = None,
    ) -> None:
        """Initialize the pipeline service with its dependencies."""
        self._session = session
        self._settings = settings or get_settings()
        self._explainer = explainer
        self._cutoff_override = cutoff

    def run(self, top_n: int | None = None) -> LinkedInMCPPipelineResult:
        """Fetch LinkedIn jobs, run matching, and return threshold-filtered results."""
        source = self._load_linkedin_source()
        registry = ConnectorRegistry([LinkedInMCPConnector(self._settings)])
        discovery = self._build_discovery(registry)
        summary = discovery.run_source(source)

        recommendations = RecommendationService(session=self._session).recommend(top_n=top_n)
        cutoff = self._cutoff()
        results = tuple(
            self._to_result(rec, cutoff) for rec in recommendations
        )
        above = sum(1 for item in results if item.above_threshold)
        return LinkedInMCPPipelineResult(
            source_id=source.id,
            source_name=source.name,
            cutoff=cutoff,
            fetched=summary.fetched_count,
            inserted=summary.inserted_count,
            duplicates=summary.duplicate_count,
            rejected=summary.rejected,
            matched_total=len(results),
            above_threshold=above,
            below_threshold=len(results) - above,
            recommendations=results,
        )

    def _load_linkedin_source(self) -> JobSourceConfig:
        """Return the active LinkedIn MCP source or raise a clear error."""
        record = self._session.scalar(
            select(JobSource)
            .where(
                JobSource.type == JobSourceType.LINKEDIN_MCP.value,
                JobSource.is_active.is_(True),
            )
            .order_by(JobSource.id)
            .limit(1)
        )
        if record is None:
            raise SourceConfigError(
                "No active linkedin_mcp source found. Add one with: "
                "stagepilot sources add-linkedin-mcp"
            )
        return JobSourceConfig(
            id=record.id,
            name=record.name,
            type=JobSourceType(record.type),
            base_url=record.base_url,
            config=record.config_json,
        )

    def _build_discovery(self, registry: ConnectorRegistry) -> DiscoveryService:
        """Build the existing discovery service over a LinkedIn-only registry."""
        return DiscoveryService(
            session=self._session,
            connector_registry=registry,
            normalizer=JobNormalizationService(),
            matching_service=JobMatchingService(
                self._session,
                HardFilterService(self._settings.filter_rules),
                DuplicateDetectionService(
                    self._session,
                    fuzzy_threshold=self._settings.filter_rules.fuzzy_title_threshold,
                ),
            ),
        )

    def _cutoff(self) -> float:
        """Return the injected or configured recommendation cutoff threshold."""
        if self._cutoff_override is not None:
            return self._cutoff_override
        return get_matching_config().thresholds.get("recommendation_cutoff", 0.0)

    def _to_result(
        self,
        rec: Recommendation,
        cutoff: float,
    ) -> LinkedInMCPRecommendationResult:
        """Convert a recommendation into a reportable result with an explanation."""
        job = self._session.get(Job, rec.job_id)
        title = job.title if job else f"Job #{rec.job_id}"
        company = job.company if job else None
        url = job.url if job else ""
        above = rec.final_score >= cutoff
        explanation = self._explain(rec, title, company)
        return LinkedInMCPRecommendationResult(
            job_id=rec.job_id,
            title=title,
            company=company,
            url=url,
            final_score=rec.final_score,
            status=rec.status.value,
            above_threshold=above,
            explanation=explanation,
            matched_skills=tuple(rec.matched_detail.matched_skills),
            missing_skills=tuple(rec.matched_detail.missing_skills),
        )

    def _explain(self, rec: Recommendation, title: str, company: str) -> str:
        """Generate a deterministic explanation from the explainable score."""
        if self._explainer is not None:
            return self._explainer(rec, title, company)
        parts = [
            f"{title} at {company or 'unknown'} matches your profile with a score of "
            f"{rec.final_score:.1f} (cutoff {self._cutoff():.1f})."
        ]
        if rec.matched_detail.matched_skills:
            parts.append(f"Matched skills: {', '.join(rec.matched_detail.matched_skills)}.")
        if rec.matched_detail.missing_skills:
            parts.append(f"Missing skills: {', '.join(rec.matched_detail.missing_skills)}.")
        if rec.insights is not None and rec.insights.summary:
            parts.append(rec.insights.summary)
        return " ".join(parts)
