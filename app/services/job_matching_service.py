from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.jobs import Job
from app.db.models.matching import JobMatch
from app.domain.matching.entities import DuplicateResult, FilterResult, RejectionReason
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService


@dataclass(slots=True)
class MutableMatchCounters:
    """Accumulated matching counters updated during a discovery run."""

    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    rejection_breakdown: dict[str, int] | None = None
    duplicate_strategy_breakdown: dict[str, int] | None = None


class JobMatchingService:
    """Orchestrate hard filtering, duplicate detection, and result persistence."""

    def __init__(
        self,
        session: Session,
        filter_service: HardFilterService,
        duplicate_service: DuplicateDetectionService,
    ) -> None:
        """Initialize the matching service with its dependencies."""
        self._session = session
        self._filter_service = filter_service
        self._duplicate_service = duplicate_service

    def process(
        self,
        job: Job,
        counters: MutableMatchCounters | None = None,
    ) -> JobMatch:
        """Apply filters and duplicate detection to a job, persist the decision."""
        existing = self._session.scalar(select(JobMatch).where(JobMatch.job_id == job.id))
        filter_result = self._filter_service.evaluate(job)
        duplicate_result = self._duplicate_service.find_duplicate(job)

        if existing is not None:
            existing.hard_filter_ok = filter_result.passed
            existing.rejection_reasons_json = self._reasons_to_dict(filter_result.rejection_reasons)
            existing.duplicate_job_id = duplicate_result.existing_job_id
            existing.duplicate_strategy = (
                duplicate_result.strategy.value if duplicate_result.strategy else None
            )
            existing.duplicate_confidence = duplicate_result.confidence
            existing.duplicate_matched_value = duplicate_result.matched_value
            match = existing
        else:
            match = JobMatch(
                job_id=job.id,
                hard_filter_ok=filter_result.passed,
                rejection_reasons_json=self._reasons_to_dict(filter_result.rejection_reasons),
                duplicate_job_id=duplicate_result.existing_job_id,
                duplicate_strategy=(
                    duplicate_result.strategy.value if duplicate_result.strategy else None
                ),
                duplicate_confidence=duplicate_result.confidence,
                duplicate_matched_value=duplicate_result.matched_value,
            )
            self._session.add(match)

        self._session.flush()

        if counters is not None:
            self._accumulate(counters, filter_result, duplicate_result)

        return match

    def process_existing(self, job: Job) -> None:
        """Run matching on an existing job that has no current match record.

        Used during migration of jobs created before Phase 2 was deployed.
        """
        existing = self._session.scalar(select(JobMatch).where(JobMatch.job_id == job.id))
        if existing is not None:
            return
        self.process(job)

    def _reasons_to_dict(
        self,
        reasons: tuple[RejectionReason, ...],
    ) -> list[dict[str, str | None]]:
        """Convert structured rejection reasons to serializable dicts."""
        return [
            {
                "category": r.category.value,
                "detail": r.detail,
                "matched_keyword": r.matched_keyword,
            }
            for r in reasons
        ]

    def _accumulate(
        self,
        counters: MutableMatchCounters,
        filter_result: FilterResult,
        duplicate_result: DuplicateResult,
    ) -> None:
        """Update counters from a single matching result."""
        if duplicate_result.is_duplicate:
            counters.duplicates += 1
            strat = duplicate_result.strategy.value if duplicate_result.strategy else "unknown"
            if counters.duplicate_strategy_breakdown is None:
                counters.duplicate_strategy_breakdown = {}
            counters.duplicate_strategy_breakdown[strat] = (
                counters.duplicate_strategy_breakdown.get(strat, 0) + 1
            )

        if filter_result.passed:
            counters.accepted += 1
        else:
            counters.rejected += 1
            if counters.rejection_breakdown is None:
                counters.rejection_breakdown = {}
            for reason in filter_result.rejection_reasons:
                cat = reason.category.value
                counters.rejection_breakdown[cat] = counters.rejection_breakdown.get(cat, 0) + 1
