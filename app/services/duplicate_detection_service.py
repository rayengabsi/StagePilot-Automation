from __future__ import annotations

from typing import ClassVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.jobs import Job, RawJob
from app.domain.matching.entities import DuplicateResult
from app.domain.matching.enums import DuplicateStrategy


class DuplicateDetectionService:
    """Detect whether a job is a duplicate of an existing job."""

    STRATEGY_ORDER: ClassVar[list[DuplicateStrategy]] = [
        DuplicateStrategy.EXTERNAL_ID,
        DuplicateStrategy.CANONICAL_URL,
        DuplicateStrategy.RAW_CONTENT_HASH,
        DuplicateStrategy.NORMALIZED_HASH,
        DuplicateStrategy.FUZZY_TITLE_COMPANY,
    ]

    def __init__(self, session: Session, fuzzy_threshold: float = 80.0) -> None:
        """Initialize with a database session and fuzzy matching threshold."""
        self._session = session
        self._threshold = fuzzy_threshold

    def find_duplicate(self, job: Job) -> DuplicateResult:
        """Run duplicate strategies in priority order and return the first match."""
        for strategy in self.STRATEGY_ORDER:
            result = self._try_strategy(job, strategy)
            if result is not None:
                return result
        return DuplicateResult(is_duplicate=False)

    def _try_strategy(self, job: Job, strategy: DuplicateStrategy) -> DuplicateResult | None:
        """Dispatch to the correct handler for a given strategy."""
        match strategy:
            case DuplicateStrategy.EXTERNAL_ID:
                return self._check_external_id(job)
            case DuplicateStrategy.CANONICAL_URL:
                return self._check_canonical_url(job)
            case DuplicateStrategy.RAW_CONTENT_HASH:
                return self._check_raw_content_hash(job)
            case DuplicateStrategy.NORMALIZED_HASH:
                return self._check_normalized_hash(job)
            case DuplicateStrategy.FUZZY_TITLE_COMPANY:
                return self._check_fuzzy_title_company(job)

    def _check_external_id(self, job: Job) -> DuplicateResult | None:
        """Strategy: match by source-level external ID."""
        if not job.external_id:
            return None
        existing = self._session.scalar(
            select(Job).where(
                Job.source_id == job.source_id,
                Job.external_id == job.external_id,
                Job.id != job.id,
            )
        )
        if existing is not None:
            return DuplicateResult(
                is_duplicate=True,
                strategy=DuplicateStrategy.EXTERNAL_ID,
                existing_job_id=existing.id,
                confidence=1.0,
                matched_value=job.external_id,
            )
        return None

    def _check_canonical_url(self, job: Job) -> DuplicateResult | None:
        """Strategy: match by normalised canonical URL."""
        normalized = job.url.strip().rstrip("/").lower()
        existing = self._session.scalar(
            select(Job).where(
                Job.id != job.id,
                func.replace(func.lower(func.trim(Job.url)), "/", "")
                == func.replace(normalized, "/", ""),
            )
        )
        if existing is not None:
            return DuplicateResult(
                is_duplicate=True,
                strategy=DuplicateStrategy.CANONICAL_URL,
                existing_job_id=existing.id,
                confidence=1.0,
                matched_value=job.url,
            )
        return None

    def _check_raw_content_hash(self, job: Job) -> DuplicateResult | None:
        """Strategy: match by raw content hash through the raw_job relationship."""
        if job.raw_job is None:
            return None
        content_hash = job.raw_job.content_hash
        existing_raw = self._session.scalar(
            select(RawJob).where(
                RawJob.source_id == job.source_id,
                RawJob.content_hash == content_hash,
                RawJob.id != job.raw_job_id,
            )
        )
        if existing_raw is not None and existing_raw.job is not None:
            return DuplicateResult(
                is_duplicate=True,
                strategy=DuplicateStrategy.RAW_CONTENT_HASH,
                existing_job_id=existing_raw.job.id,
                confidence=1.0,
                matched_value=content_hash[:16],
            )
        return None

    def _check_normalized_hash(self, job: Job) -> DuplicateResult | None:
        """Strategy: match by deterministic normalised hash."""
        existing = self._session.scalar(
            select(Job).where(
                Job.source_id == job.source_id,
                Job.normalized_hash == job.normalized_hash,
                Job.id != job.id,
            )
        )
        if existing is not None:
            return DuplicateResult(
                is_duplicate=True,
                strategy=DuplicateStrategy.NORMALIZED_HASH,
                existing_job_id=existing.id,
                confidence=1.0,
                matched_value=job.normalized_hash[:16],
            )
        return None

    def _check_fuzzy_title_company(self, job: Job) -> DuplicateResult | None:
        """Strategy: match by similar title and same company using RapidFuzz."""
        if not job.company:
            return None

        candidates = self._session.scalars(
            select(Job).where(
                Job.company == job.company,
                Job.id != job.id,
            )
        ).all()

        from rapidfuzz import fuzz

        best_score = 0.0
        best_job_id: int | None = None
        best_title: str | None = None

        for candidate in candidates:
            score = fuzz.token_sort_ratio(job.title or "", candidate.title or "")
            if score > best_score:
                best_score = score
                best_job_id = candidate.id
                best_title = candidate.title

        if best_job_id is not None and best_score >= self._threshold:
            return DuplicateResult(
                is_duplicate=True,
                strategy=DuplicateStrategy.FUZZY_TITLE_COMPANY,
                existing_job_id=best_job_id,
                confidence=round(best_score / 100.0, 4),
                matched_value=best_title,
            )
        return None
