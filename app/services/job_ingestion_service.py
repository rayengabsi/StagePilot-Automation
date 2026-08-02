from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.jobs import Job, RawJob
from app.domain.jobs.classification import JobClassification
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig, NormalizedJob
from app.shared.hashing import stable_sha256


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Result of attempting to ingest one discovered job."""

    inserted: bool
    duplicate: bool
    raw_job_id: int | None = None
    job_id: int | None = None
    reason: str | None = None


class JobIngestionService:
    """Persist raw and normalized jobs with duplicate protection."""

    def __init__(self, session: Session) -> None:
        """Initialize the service with a database session."""
        self._session = session

    def ingest(
        self,
        source: JobSourceConfig,
        discovered: DiscoveredJob,
        normalized: NormalizedJob,
        classification: JobClassification | None = None,
    ) -> IngestionResult:
        """Persist one discovered job if it has not already been ingested.

        *classification* is stored as normalized intelligence alongside the
        original connector-extracted values; it never affects duplicate
        detection because it is derived from the same normalized job.
        """
        content_hash = self._content_hash(source, discovered)
        raw_duplicate = self._find_raw_duplicate(source.id, discovered.external_id, content_hash)
        if raw_duplicate is not None:
            return IngestionResult(
                inserted=False,
                duplicate=True,
                raw_job_id=raw_duplicate.id,
                reason="raw_duplicate",
            )

        normalized_hash = self._normalized_hash(normalized)
        job_duplicate = self._find_job_duplicate(source.id, normalized_hash)
        if job_duplicate is None:
            job_duplicate = self._find_cross_source_duplicate(normalized)
        if job_duplicate is not None:
            return IngestionResult(
                inserted=False,
                duplicate=True,
                job_id=job_duplicate.id,
                reason="normalized_duplicate",
            )

        raw_job = RawJob(
            source_id=source.id,
            external_id=discovered.external_id,
            url=discovered.url,
            raw_payload_json=discovered.raw_payload,
            content_hash=content_hash,
            discovered_at=discovered.discovered_at,
        )
        self._session.add(raw_job)
        self._session.flush()

        job = Job(
            raw_job_id=raw_job.id,
            source_id=source.id,
            external_id=normalized.external_id,
            url=normalized.url,
            title=normalized.title,
            company=normalized.company,
            location=normalized.location,
            description=normalized.description,
            requirements=normalized.requirements,
            department=normalized.department,
            employment_type=normalized.employment_type,
            remote_status=normalized.remote_status,
            classification_specialization=(
                classification.specialization if classification else None
            ),
            classification_seniority=classification.seniority if classification else None,
            classification_employment_type=(
                classification.employment_type if classification else None
            ),
            classification_work_mode=classification.work_mode if classification else None,
            classification_urgency=classification.urgency if classification else None,
            normalized_hash=normalized_hash,
            posted_at=normalized.posted_at,
        )
        self._session.add(job)
        self._session.flush()

        return IngestionResult(inserted=True, duplicate=False, raw_job_id=raw_job.id, job_id=job.id)

    def _find_raw_duplicate(
        self, source_id: int, external_id: str | None, content_hash: str
    ) -> RawJob | None:
        """Find an existing raw job by external ID or content hash."""
        if external_id:
            existing = self._session.scalar(
                select(RawJob).where(
                    RawJob.source_id == source_id, RawJob.external_id == external_id
                )
            )
            if existing is not None:
                return existing

        return self._session.scalar(
            select(RawJob).where(RawJob.source_id == source_id, RawJob.content_hash == content_hash)
        )

    def _find_job_duplicate(self, source_id: int, normalized_hash: str) -> Job | None:
        """Find an existing normalized job by source and normalized hash."""
        return self._session.scalar(
            select(Job).where(Job.source_id == source_id, Job.normalized_hash == normalized_hash)
        )

    def _find_cross_source_duplicate(self, job: NormalizedJob) -> Job | None:
        """Find an existing job from any source with the same canonical URL.

        This merges the same posting discovered through multiple providers,
        keeping a single canonical job record per URL.
        """
        normalized = job.url.strip().rstrip("/").lower()
        if not normalized:
            return None
        return self._session.scalar(
            select(Job).where(
                func.replace(func.lower(func.trim(Job.url)), "/", "")
                == func.replace(normalized, "/", "")
            )
        )

    def _content_hash(self, source: JobSourceConfig, job: DiscoveredJob) -> str:
        """Compute the raw content hash used for ingestion duplicate protection."""
        return stable_sha256(
            {
                "source_type": source.type.value,
                "external_id": job.external_id,
                "url": job.url,
                "title": job.title,
                "description": job.description,
            }
        )

    def _normalized_hash(self, job: NormalizedJob) -> str:
        """Compute the normalized job hash used for duplicate protection."""
        return stable_sha256(
            {
                "url": job.url,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "description": job.description,
            }
        )
