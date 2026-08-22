"""Tests for the StagePilot HTTP API.

Uses an in-memory SQLite database via the integration fixture and FastAPI's
TestClient so no real MySQL, LinkedIn, or Telegram is touched.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.api.app import create_app
from app.api.dependencies import set_session_factory
from app.db.base import Base, import_models
from app.db.models.job_filter import JobFilter
from app.db.models.jobs import Job, JobSource, RawJob
from app.db.models.recommendation import RecommendationRecord
from app.domain.job_filters.entities import JobFilterRules
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db() -> Iterator[Session]:
    import_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db: Session) -> Iterator[TestClient]:
    app = create_app()
    # Use the SAME engine so the API handler reads the same in-memory DB.
    bind = db.get_bind()
    set_session_factory(sessionmaker(bind=bind, expire_on_commit=False))
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    set_session_factory(None)


# ── health ────────────────────────────────────────────────────────────────────


def test_health_returns_200(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── profile ───────────────────────────────────────────────────────────────────


def test_profile_no_profile_returns_404(client: TestClient) -> None:
    resp = client.get("/api/profile")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "profile_not_found"


def _seed_profile(db: Session) -> None:
    from app.db.models.profile import EducationRecord, Profile, SkillRecord

    profile = Profile(name="Test", active=True)
    db.add(profile)
    db.flush()
    db.add(EducationRecord(profile_id=profile.id, institution="MIT", degree="BS"))
    db.add(SkillRecord(profile_id=profile.id, name="Python", category="language"))
    db.commit()


def test_profile_with_data_returns_200(client: TestClient, db: Session) -> None:
    _seed_profile(db)
    resp = client.get("/api/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert "personal_info" in body
    assert "completeness" in body
    assert body["skills"][0]["name"] == "Python"


# ── filters ───────────────────────────────────────────────────────────────────


def test_filters_returns_defaults(client: TestClient) -> None:
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unknown_data_policy"] == "accept"
    assert body["excluded_keywords"] == []
    assert body["remote_only"] is False


def test_filters_returns_persisted_rules(client: TestClient, db: Session) -> None:
    rules = JobFilterRules(required_titles=["engineer"], remote_only=True)
    db.add(JobFilter(id=1, rules_json=rules.model_dump()))
    db.commit()
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    body = resp.json()
    assert body["required_titles"] == ["engineer"]
    assert body["remote_only"] is True


# ── scheduler ─────────────────────────────────────────────────────────────────


def test_scheduler_status_returns_expected_keys(client: TestClient) -> None:
    resp = client.get("/api/scheduler/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "enabled" in body
    assert "running" in body
    assert "interval_minutes" in body
    assert body["enabled"] is False


# ── jobs ──────────────────────────────────────────────────────────────────────


def test_jobs_empty_database(client: TestClient) -> None:
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


_job_counter = 0


def _seed_job(db: Session, *, title: str = "SWE Intern", company: str = "Acme") -> int:
    global _job_counter
    _job_counter += 1
    from datetime import UTC, datetime

    now = datetime.now(tz=UTC)
    source = JobSource(name=f"test-src-{_job_counter}", type="test", base_url="http://x")
    db.add(source)
    db.flush()
    raw = RawJob(
        source_id=source.id,
        url=f"http://x/{_job_counter}",
        raw_payload_json={},
        content_hash=f"h{_job_counter}",
        discovered_at=now,
    )
    db.add(raw)
    db.flush()
    job = Job(
        raw_job_id=raw.id,
        source_id=source.id,
        url=f"http://x/job/{_job_counter}",
        title=title,
        company=company,
        normalized_hash=f"abc{_job_counter}",
    )
    db.add(job)
    db.commit()
    return job.id


def test_jobs_pagination(client: TestClient, db: Session) -> None:
    _seed_job(db, title="A")
    _seed_job(db, title="B")
    _seed_job(db, title="C")
    resp = client.get("/api/jobs?limit=2&offset=0")
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    resp2 = client.get("/api/jobs?limit=2&offset=2")
    body2 = resp2.json()
    assert len(body2["items"]) == 1


def test_jobs_serialize_correctly(client: TestClient, db: Session) -> None:
    _seed_job(db, title="Backend Dev", company="Stark")
    resp = client.get("/api/jobs")
    item = resp.json()["items"][0]
    assert item["title"] == "Backend Dev"
    assert item["company"] == "Stark"
    assert item["id"] > 0


# ── matches ───────────────────────────────────────────────────────────────────


def test_matches_empty_database(client: TestClient) -> None:
    resp = client.get("/api/matches")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_matches_pagination_and_serialization(client: TestClient, db: Session) -> None:
    from app.db.models.profile import Profile

    profile = Profile(name="Test", active=True)
    db.add(profile)
    db.flush()
    job_id = _seed_job(db, title="ML Intern")
    rec = RecommendationRecord(
        profile_id=profile.id,
        job_id=job_id,
        final_score=78.5,
        ranking_position=1,
        status="active",
        matched_skills_json=["Python", "ML"],
        missing_skills_json=["PyTorch"],
        matched_technologies_json=["FastAPI"],
        missing_technologies_json=[],
        hard_rule_passed=True,
        insights_json={"explanation": "Strong Python match."},
    )
    db.add(rec)
    db.commit()

    resp = client.get("/api/matches?limit=10")
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["final_score"] == 78.5
    assert item["matched_skills"] == ["Python", "ML"]
    assert item["job_title"] == "ML Intern"
    assert item["explanation"] == "Strong Python match."


# ── error handling ────────────────────────────────────────────────────────────


def test_unknown_route_returns_404(client: TestClient) -> None:
    resp = client.get("/api/nonexistent")
    assert resp.status_code == 404


# ── docs ──────────────────────────────────────────────────────────────────────


def test_openapi_docs_are_accessible(client: TestClient) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_openapi_json_is_accessible(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert "/api/health" in schema["paths"]
    assert "/api/profile" in schema["paths"]
