from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.jobs import Job
from app.db.models.matching import JobMatch
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.errors import DiscoveryError, JobNormalizationError
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.services.job_ingestion_service import JobIngestionService
from app.services.job_matching_service import JobMatchingService, MutableMatchCounters
from app.services.job_normalization_service import JobNormalizationService
from app.services.job_source_repository import JobSourceRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscoverySummary:
    """Summary of a discovery run including filtering and duplicate metrics."""

    run_id: str
    sources_count: int
    fetched_count: int
    inserted_count: int
    duplicate_count: int
    invalid_count: int
    failed_sources_count: int
    accepted: int
    rejected: int
    semantic_duplicates: int
    rejection_breakdown: dict[str, int]
    duplicate_strategy_breakdown: dict[str, int]
    duration_seconds: float


class DiscoveryService:
    """Orchestrate source fetching, normalization, ingestion, and matching."""

    def __init__(
        self,
        session: Session,
        connector_registry: ConnectorRegistry,
        normalizer: JobNormalizationService,
        matching_service: JobMatchingService,
    ) -> None:
        """Initialize the discovery service dependencies."""
        self._session = session
        self._sources = JobSourceRepository(session)
        self._ingestion = JobIngestionService(session)
        self._registry = connector_registry
        self._normalizer = normalizer
        self._matching = matching_service

    def run_once(self, backfill_existing: bool = False) -> DiscoverySummary:
        """Run discovery once across all active configured sources.

        When *backfill_existing* is True, all existing jobs without a
        ``JobMatch`` record are also processed during this run.
        """
        run_id = str(uuid4())
        source_configs = self._sources.list_active_configs()
        summary = _MutableDiscoverySummary(
            run_id=run_id,
            sources_count=len(source_configs),
            match_counters=MutableMatchCounters(),
        )
        started = time.monotonic()
        logger.info(
            "discovery_started", extra={"run_id": run_id, "sources_count": len(source_configs)}
        )

        for source in source_configs:
            self._discover_source(source, summary)

        if backfill_existing:
            self._backfill_existing(summary)

        summary.duration_seconds = time.monotonic() - started
        result = summary.freeze()
        logger.info("discovery_completed", extra=asdict(result))
        return result

    def _discover_source(self, source: JobSourceConfig, summary: _MutableDiscoverySummary) -> None:
        """Discover and ingest jobs from one source."""
        logger.info(
            "source_discovery_started",
            extra={
                "run_id": summary.run_id,
                "source_id": source.id,
                "source_name": source.name,
                "source_type": source.type.value,
            },
        )
        try:
            connector = self._registry.get(source.type)
            discovered_jobs = connector.fetch(source)
            summary.fetched_count += len(discovered_jobs)
            logger.info(
                "source_fetch_succeeded",
                extra={
                    "run_id": summary.run_id,
                    "source_id": source.id,
                    "items_count": len(discovered_jobs),
                },
            )
            for discovered in discovered_jobs:
                try:
                    normalized = self._normalizer.normalize(discovered)
                    result = self._ingestion.ingest(source, discovered, normalized)
                except JobNormalizationError as exc:
                    summary.invalid_count += 1
                    logger.warning(
                        "job_invalid_skipped",
                        extra={
                            "run_id": summary.run_id,
                            "source_id": source.id,
                            "reason": str(exc),
                        },
                    )
                    continue

                if result.duplicate:
                    summary.duplicate_count += 1
                    logger.info(
                        "job_duplicate_skipped",
                        extra={
                            "run_id": summary.run_id,
                            "source_id": source.id,
                            "reason": result.reason,
                            "url": discovered.url,
                        },
                    )
                elif result.job_id is not None:
                    summary.inserted_count += 1
                    logger.info(
                        "job_ingested",
                        extra={
                            "run_id": summary.run_id,
                            "source_id": source.id,
                            "raw_job_id": result.raw_job_id,
                            "job_id": result.job_id,
                            "url": discovered.url,
                        },
                    )
                    self._process_job(result.job_id, summary)
            self._session.commit()
        except DiscoveryError as exc:
            self._session.rollback()
            summary.failed_sources_count += 1
            logger.exception(
                "source_discovery_failed",
                extra={
                    "run_id": summary.run_id,
                    "source_id": source.id,
                    "error_type": type(exc).__name__,
                },
            )

    def _process_job(self, job_id: int, summary: _MutableDiscoverySummary) -> None:
        """Apply filters and duplicate detection to a single ingested job."""
        job = self._session.get(Job, job_id)
        if job is None:
            return
        self._matching.process(job, counters=summary.match_counters)

    def _backfill_existing(self, summary: _MutableDiscoverySummary) -> None:
        """Create match records for jobs that were ingested before Phase 2."""
        job_ids = self._session.scalars(
            select(Job.id).where(
                Job.id.notin_(select(JobMatch.job_id).where(JobMatch.job_id == Job.id))
            )
        ).all()
        for jid in job_ids:
            job = self._session.get(Job, jid)
            if job is not None:
                self._matching.process(job, counters=summary.match_counters)
        if job_ids:
            self._session.commit()


@dataclass(slots=True)
class _MutableDiscoverySummary:
    """Mutable discovery counters used while a run is in progress."""

    run_id: str
    sources_count: int
    fetched_count: int = 0
    inserted_count: int = 0
    duplicate_count: int = 0
    invalid_count: int = 0
    failed_sources_count: int = 0
    duration_seconds: float = 0.0
    match_counters: MutableMatchCounters | None = None

    def freeze(self) -> DiscoverySummary:
        """Return an immutable discovery summary."""
        ac = self.match_counters
        return DiscoverySummary(
            run_id=self.run_id,
            sources_count=self.sources_count,
            fetched_count=self.fetched_count,
            inserted_count=self.inserted_count,
            duplicate_count=self.duplicate_count,
            invalid_count=self.invalid_count,
            failed_sources_count=self.failed_sources_count,
            accepted=ac.accepted if ac else 0,
            rejected=ac.rejected if ac else 0,
            semantic_duplicates=ac.duplicates if ac else 0,
            rejection_breakdown=ac.rejection_breakdown or {} if ac else {},
            duplicate_strategy_breakdown=ac.duplicate_strategy_breakdown or {} if ac else {},
            duration_seconds=round(self.duration_seconds, 3),
        )
