from __future__ import annotations

from app.db.base import Base
from app.db.models.jobs import Job, JobSource, RawJob
from app.services.duplicate_detection_service import DuplicateDetectionService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _session() -> Session:
    """Create an isolated in-memory SQLAlchemy session."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _insert_source(session: Session, name: str = "Test Source") -> JobSource:
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
    company: str = "Example",
    external_id: str | None = "ext-1",
    url: str = "https://example.com/jobs/1",
    location: str = "Tunisia",
    description: str = "Python backend internship.",
    normalized_hash: str | None = None,
) -> Job:
    import hashlib
    import re

    raw_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    if normalized_hash is None:
        normalized_hash = hashlib.sha256(
            re.sub(r"\s+", " ", (title + company + url).lower()).encode()
        ).hexdigest()[:16]
    raw = RawJob(
        source_id=source.id,
        external_id=external_id,
        url=url,
        raw_payload_json={},
        content_hash=raw_hash,
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
        normalized_hash=normalized_hash,
    )
    session.add(job)
    session.flush()
    return job


class TestExternalIdStrategy:
    """Duplicate detection via source-level external ID."""

    def test_matches_exact_external_id(self) -> None:
        session = _session()
        source = _insert_source(session)
        existing = _insert_job(session, source, external_id="ext-1")
        candidate = _insert_job(
            session, source, external_id="ext-1", url="https://example.com/jobs/2"
        )
        service = DuplicateDetectionService(session)
        result = service.find_duplicate(candidate)
        assert result.is_duplicate
        assert result.existing_job_id == existing.id
        assert result.strategy is not None
        assert result.strategy.value == "external_id"

    def test_no_match_when_external_id_differs(self) -> None:
        session = _session()
        source = _insert_source(session)
        _insert_job(session, source, external_id="ext-1")
        candidate = _insert_job(
            session,
            source,
            external_id="ext-2",
            title="Completely Different Role",
            company="OtherCorp",
            url="https://example.com/jobs/2",
        )
        service = DuplicateDetectionService(session)
        result = service.find_duplicate(candidate)
        assert not result.is_duplicate


class TestFuzzyTitleCompanyStrategy:
    """Duplicate detection via fuzzy title and same company."""

    def test_matches_similar_title_same_company(self) -> None:
        session = _session()
        source = _insert_source(session)
        _insert_job(session, source, title="Software Engineering Internship", company="Example")
        candidate = _insert_job(
            session,
            source,
            title="Software Engineer Intern",
            company="Example",
            url="https://example.com/jobs/2",
            external_id="ext-2",
        )
        service = DuplicateDetectionService(session, fuzzy_threshold=60.0)
        result = service.find_duplicate(candidate)
        assert result.is_duplicate
        assert result.strategy is not None
        assert result.strategy.value == "fuzzy_title_company"

    def test_no_match_different_company(self) -> None:
        session = _session()
        source = _insert_source(session)
        _insert_job(session, source, title="Software Engineering Internship", company="CompanyA")
        candidate = _insert_job(
            session,
            source,
            title="Software Engineering Internship",
            company="CompanyB",
            url="https://example.com/jobs/2",
            external_id="ext-2",
        )
        service = DuplicateDetectionService(session, fuzzy_threshold=60.0)
        result = service.find_duplicate(candidate)
        assert not result.is_duplicate

    def test_no_match_very_different_titles(self) -> None:
        session = _session()
        source = _insert_source(session)
        _insert_job(session, source, title="Marketing Intern", company="Example")
        candidate = _insert_job(
            session,
            source,
            title="Senior Data Scientist",
            company="Example",
            url="https://example.com/jobs/2",
            external_id="ext-2",
        )
        service = DuplicateDetectionService(session, fuzzy_threshold=80.0)
        result = service.find_duplicate(candidate)
        assert not result.is_duplicate


class TestStrategyPriority:
    """Strategies should be tried in priority order."""

    def test_external_id_takes_priority(self) -> None:
        session = _session()
        source = _insert_source(session)
        _insert_job(session, source, external_id="ext-1", title="Original Title")
        candidate = _insert_job(
            session,
            source,
            external_id="ext-1",
            title="Very Different Title",
            url="https://example.com/jobs/2",
        )
        service = DuplicateDetectionService(session)
        result = service.find_duplicate(candidate)
        assert result.strategy is not None
        assert result.strategy.value == "external_id"

    def test_normalized_hash_when_no_external_id(self) -> None:
        session = _session()
        source_a = _insert_source(session, name="Source A")
        source_b = _insert_source(session, name="Source B")
        _insert_job(session, source_a, external_id=None, normalized_hash="same-hash")
        candidate = _insert_job(
            session,
            source_b,
            external_id="new-ext",
            normalized_hash="same-hash",
            url="https://example.com/jobs/2",
        )
        service = DuplicateDetectionService(session)
        result = service.find_duplicate(candidate)
        assert result.is_duplicate
