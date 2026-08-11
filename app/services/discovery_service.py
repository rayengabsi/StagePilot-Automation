from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.discovery import DiscoveryMetricRecord
from app.db.models.jobs import Job
from app.db.models.matching import JobMatch
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.errors import DiscoveryError, JobNormalizationError
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.services.job_classification_service import JobClassificationService
from app.services.job_ingestion_service import JobIngestionService
from app.services.job_matching_service import JobMatchingService, MutableMatchCounters
from app.services.job_normalization_service import JobNormalizationService
from app.services.job_source_repository import JobSourceRepository
from app.services.user_filter_service import UserFilterService

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
    inserted_job_ids: tuple[int, ...] = ()
    source_errors: tuple[str, ...] = ()
    filtered_count: int = 0
    filtered_job_ids: tuple[int, ...] = ()
    filter_rejection_breakdown: dict[str, int] = field(default_factory=dict)


class DiscoveryService:
    """Orchestrate source fetching, normalization, ingestion, and matching."""

    def __init__(
        self,
        session: Session,
        connector_registry: ConnectorRegistry,
        normalizer: JobNormalizationService,
        matching_service: JobMatchingService,
        classifier: JobClassificationService | None = None,
        user_filter_service: UserFilterService | None = None,
    ) -> None:
        """Initialize the discovery service dependencies.

        *classifier* enriches every normalized job with structured
        intelligence (specialization, seniority, employment type, work mode,
        urgency) immediately after normalization and before ingestion. When
        omitted the default JobClassificationService is used.

        *user_filter_service* applies the user-controlled hard filter stage to
        every job inserted during *this* run, before the job reaches the
        existing matching/scoring stage. Filtered jobs are never matched or
        delivered. When omitted no user filtering is applied.
        """
        self._session = session
        self._sources = JobSourceRepository(session)
        self._ingestion = JobIngestionService(session)
        self._registry = connector_registry
        self._normalizer = normalizer
        self._matching = matching_service
        self._classifier = classifier or JobClassificationService()
        self._user_filter_service = user_filter_service

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

    def run_source(self, source: JobSourceConfig) -> DiscoverySummary:
        """Run discovery for a single configured source and persist metrics."""
        run_id = str(uuid4())
        summary = _MutableDiscoverySummary(
            run_id=run_id,
            sources_count=1,
            match_counters=MutableMatchCounters(),
        )
        started = time.monotonic()
        self._discover_source(source, summary)
        summary.duration_seconds = time.monotonic() - started
        result = summary.freeze()
        logger.info("source_discovery_completed", extra=asdict(result))
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
        source_started = time.monotonic()
        source_stats = _SourceStats()
        try:
            connector = self._registry.get(source.type)
            discovered_jobs = connector.fetch(source)
            summary.fetched_count += len(discovered_jobs)
            source_stats.jobs_fetched = len(discovered_jobs)
            logger.info(
                "source_fetch_succeeded",
                extra={
                    "run_id": summary.run_id,
                    "source_id": source.id,
                    "items_count": len(discovered_jobs),
                },
            )
            counters_before = _snapshot_counters(summary.match_counters)
            for discovered in discovered_jobs:
                try:
                    normalized = self._normalizer.normalize(discovered)
                    classification = self._classifier.classify(normalized)
                    result = self._ingestion.ingest(source, discovered, normalized, classification)
                except JobNormalizationError as exc:
                    summary.invalid_count += 1
                    source_stats.invalid += 1
                    logger.warning(
                        "job_invalid_skipped",
                        extra={
                            "run_id": summary.run_id,
                            "source_id": source.id,
                            "reason": str(exc),
                        },
                    )
                    continue
                except Exception as exc:
                    summary.invalid_count += 1
                    source_stats.invalid += 1
                    logger.warning(
                        "job_error_skipped",
                        extra={
                            "run_id": summary.run_id,
                            "source_id": source.id,
                            "error_type": type(exc).__name__,
                            "reason": str(exc),
                        },
                    )
                    continue

                if result.duplicate:
                    summary.duplicate_count += 1
                    source_stats.duplicates += 1
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
                    summary.inserted_job_ids.append(result.job_id)
                    source_stats.jobs_inserted += 1
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
                    if self._user_filter_service is not None and self._is_filtered_out(
                        result.job_id, summary
                    ):
                        continue
                    self._process_job(result.job_id, summary)
            counters_after = _snapshot_counters(summary.match_counters)
            source_stats.accepted = counters_after["accepted"] - counters_before["accepted"]
            source_stats.rejected = counters_after["rejected"] - counters_before["rejected"]
            source_stats.latency_ms = round((time.monotonic() - source_started) * 1000, 2)
            self._record_metric(source, summary.run_id, source_stats)
            self._session.commit()
        except DiscoveryError as exc:
            self._handle_source_failure(source, summary, source_stats, source_started, exc)
        except Exception as exc:
            self._handle_source_failure(source, summary, source_stats, source_started, exc)

    def _handle_source_failure(
        self,
        source: JobSourceConfig,
        summary: _MutableDiscoverySummary,
        stats: _SourceStats,
        started: float,
        exc: Exception,
    ) -> None:
        """Record a failed source run without interrupting other sources.

        A failure in one provider is isolated to that source: the run-level
        summary is updated, a metric record is persisted, and discovery
        continues with the next configured source.
        """
        self._session.rollback()
        summary.failed_sources_count += 1
        summary.source_errors.append(f"{source.name}: {exc}")
        stats.status = "failed"
        stats.error = str(exc)
        stats.latency_ms = round((time.monotonic() - started) * 1000, 2)
        self._record_metric(source, summary.run_id, stats)
        self._session.commit()
        logger.exception(
            "source_discovery_failed",
            extra={
                "run_id": summary.run_id,
                "source_id": source.id,
                "error_type": type(exc).__name__,
            },
        )

    def _record_metric(
        self,
        source: JobSourceConfig,
        run_id: str,
        stats: _SourceStats,
    ) -> None:
        """Persist a discovery metric record for a single source."""
        self._session.add(
            DiscoveryMetricRecord(
                run_id=run_id,
                source_id=source.id,
                source_name=source.name,
                provider=source.type.value,
                jobs_fetched=stats.jobs_fetched,
                jobs_inserted=stats.jobs_inserted,
                duplicates=stats.duplicates,
                invalid=stats.invalid,
                accepted=stats.accepted,
                rejected=stats.rejected,
                latency_ms=stats.latency_ms,
                status=stats.status,
                error=stats.error,
            )
        )

    def _process_job(self, job_id: int, summary: _MutableDiscoverySummary) -> None:
        """Apply filters and duplicate detection to a single ingested job."""
        job = self._session.get(Job, job_id)
        if job is None:
            return
        self._matching.process(job, counters=summary.match_counters)

    def _is_filtered_out(self, job_id: int, summary: _MutableDiscoverySummary) -> bool:
        """Apply the user filter stage and record whether the job is excluded.

        Filtered jobs are removed from the current run's eligible set (they are
        never matched, scored, or delivered) and their rejection is attributed
        to the exact structured rule identifier in the breakdown.
        """
        job = self._session.get(Job, job_id)
        if job is None or self._user_filter_service is None:
            return False
        result = self._user_filter_service.evaluate(job)
        if result.passed:
            return False
        summary.filtered_count += 1
        summary.filtered_job_ids.append(job_id)
        for rejection in result.rejections:
            code = rejection.code.value
            summary.filter_rejection_breakdown[code] = (
                summary.filter_rejection_breakdown.get(code, 0) + 1
            )
        logger.info(
            "job_user_filtered",
            extra={
                "run_id": summary.run_id,
                "job_id": job_id,
                "rejection": result.rejections[0].code.value if result.rejections else None,
            },
        )
        return True

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


def _snapshot_counters(counters: MutableMatchCounters | None) -> dict[str, int]:
    """Snapshot the match counters for per-source metric deltas."""
    if counters is None:
        return {"accepted": 0, "rejected": 0, "duplicates": 0}
    return {
        "accepted": counters.accepted,
        "rejected": counters.rejected,
        "duplicates": counters.duplicates,
    }


@dataclass(slots=True)
class _SourceStats:
    """Per-source counters used to build a discovery metric record."""

    jobs_fetched: int = 0
    jobs_inserted: int = 0
    duplicates: int = 0
    invalid: int = 0
    accepted: int = 0
    rejected: int = 0
    latency_ms: float | None = None
    status: str = "ok"
    error: str | None = None


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
    inserted_job_ids: list[int] = field(default_factory=list)
    source_errors: list[str] = field(default_factory=list)
    filtered_count: int = 0
    filtered_job_ids: list[int] = field(default_factory=list)
    filter_rejection_breakdown: dict[str, int] = field(default_factory=dict)

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
            inserted_job_ids=tuple(self.inserted_job_ids),
            source_errors=tuple(self.source_errors),
            filtered_count=self.filtered_count,
            filtered_job_ids=tuple(self.filtered_job_ids),
            filter_rejection_breakdown=dict(self.filter_rejection_breakdown),
        )
