from __future__ import annotations

from app.config.settings import FilterRules
from app.db.base import Base
from app.db.models.jobs import Job, JobSource, RawJob
from app.db.models.matching import JobMatch
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService, MutableMatchCounters
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _insert_source(session: Session, name: str = "Source") -> JobSource:
    source = JobSource(
        name=name, type="rss_feed", base_url="https://example.com/rss", config_json={}
    )
    session.add(source)
    session.flush()
    return source


def _insert_job(
    session: Session,
    source: JobSource,
    title: str = "PFE Internship",
    external_id: str | None = "ext-1",
    url: str = "https://example.com/jobs/1",
    company: str = "Example",
    location: str = "Tunisia",
    description: str = "Python backend internship.",
) -> Job:
    raw = RawJob(
        source_id=source.id,
        external_id=external_id,
        url=url,
        raw_payload_json={},
        content_hash=f"raw-{url}",
        discovered_at=__import__("datetime").datetime.now(),
    )
    session.add(raw)
    session.flush()
    job = Job(
        raw_job_id=raw.id,
        source_id=source.id,
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        location=location,
        description=description,
        normalized_hash=f"norm-{url}",
    )
    session.add(job)
    session.flush()
    return job


def _service(session: Session) -> tuple[JobMatchingService, HardFilterService]:
    filter_svc = HardFilterService(FilterRules())
    duplicate_svc = DuplicateDetectionService(session)
    matching_svc = JobMatchingService(session, filter_svc, duplicate_svc)
    return matching_svc, filter_svc


class TestJobMatchingService:
    """Integration tests for the full matching pipeline."""

    def test_creates_match_record_for_valid_job(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(session, source)
        matching_svc = _service(session)[0]
        match = matching_svc.process(job)
        assert match.job_id == job.id
        assert match.hard_filter_ok is True

    def test_creates_match_record_with_rejection(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(session, source, title="Senior Manager", description="Full-time CDI")
        matching_svc = _service(session)[0]
        match = matching_svc.process(job)
        assert match.hard_filter_ok is False
        assert match.rejection_reasons_json is not None
        assert len(match.rejection_reasons_json) > 0

    def test_updates_existing_match_record(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(session, source)
        matching_svc = _service(session)[0]
        first = matching_svc.process(job)
        match_id = first.id
        second = matching_svc.process(job)
        assert second.id == match_id

    def test_accumulates_counters_for_accepted_job(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(session, source)
        matching_svc = _service(session)[0]
        counters = MutableMatchCounters()
        matching_svc.process(job, counters=counters)
        assert counters.accepted == 1
        assert counters.rejected == 0

    def test_accumulates_counters_for_rejected_job(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(
            session, source, title="Senior Marketing Manager", description="Full-time"
        )
        matching_svc = _service(session)[0]
        counters = MutableMatchCounters()
        matching_svc.process(job, counters=counters)
        assert counters.accepted == 0
        assert counters.rejected >= 1

    def test_process_existing_skips_if_match_exists(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(session, source)
        matching_svc = _service(session)[0]
        matching_svc.process(job)
        before_count = session.scalar(select(func.count()).select_from(JobMatch))
        matching_svc.process_existing(job)
        after_count = session.scalar(select(func.count()).select_from(JobMatch))
        assert after_count == before_count

    def test_process_existing_creates_match_if_missing(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(session, source)
        matching_svc = _service(session)[0]
        matching_svc.process_existing(job)
        match = session.scalar(select(JobMatch).where(JobMatch.job_id == job.id))
        assert match is not None


class TestRejectionReasonSerialisation:
    """Rejection reasons should be serialised to JSON-friendly dicts."""

    def test_each_reason_has_required_keys(self) -> None:
        session = _session()
        source = _insert_source(session)
        job = _insert_job(
            session, source, title="Senior Lead Director", location="USA", description=""
        )
        matching_svc = _service(session)[0]
        match = matching_svc.process(job)
        assert match.rejection_reasons_json is not None
        for reason in match.rejection_reasons_json:
            assert "category" in reason
            assert "detail" in reason
            assert isinstance(reason["category"], str)
            assert isinstance(reason["detail"], str)
