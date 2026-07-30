"""End-to-end integration tests: resume import to profile management."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.db.models.profile import Profile, ProfileVersionRecord
from app.domain.master_profile.entities import MasterProfile
from app.domain.master_profile.errors import ProfileNotFoundError
from app.infrastructure.parsers.markdown_parser import MarkdownParser
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.profile_normalizer import ProfileNormalizer
from app.services.profile_service import ProfileService
from app.services.profile_validator import ProfileValidator
from sqlalchemy import select
from sqlalchemy.orm import Session


def _make_resume(tmp_path: Path) -> Path:
    content = """John Doe
john@example.com
+21653852323
https://github.com/johndoe
https://linkedin.com/in/johndoe

Summary
Experienced software engineer with 5 years in full-stack development.

Education
University of Tunis
Master in Computer Science
2019 2023

Experience
Tech Corp
Software Engineer
2023 2024
Developed microservices using Python and Docker.
Python
Docker
Kubernetes

Skills
Python, Java, SQL, Docker, Kubernetes, React, TypeScript, AWS

Languages
English (fluent), French (native)

Certifications
AWS Certified Solutions Architect, Google Cloud Associate

Projects
E-commerce Platform
Built full-stack e-commerce site.
Python, Django, React
https://github.com/johndoe/ecommerce

Awards
Best Innovation Award

Publications
Building Scalable Microservices
"""
    path = tmp_path / "resume.md"
    path.write_text(content, encoding="utf-8")
    return path


def _service(db_session: Session) -> ProfileService:
    return ProfileService(
        session=db_session,
        parser=MarkdownParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )


def test_full_pipeline_with_master_profile(db_session: Session, tmp_path: Path) -> None:
    resume = _make_resume(tmp_path)
    service = _service(db_session)
    profile = service.import_resume(resume)
    assert isinstance(profile, MasterProfile)
    assert profile.personal_info.full_name == "John Doe"
    assert profile.personal_info.email == "john@example.com"
    completeness = service.get_completeness()
    assert completeness.score > 0

    profile_row = db_session.scalar(select(Profile).limit(1))
    assert profile_row is not None
    assert profile_row.active is True

    versions = db_session.scalars(
        select(ProfileVersionRecord).order_by(ProfileVersionRecord.version_number.desc())
    ).all()
    assert len(versions) >= 1

    profiles = service.list_profiles()
    assert len(profiles) == 1
    assert profiles[0]["active"] is True
    assert profiles[0]["full_name"] == "John Doe"


def test_markdown_parsing_and_activation(db_session: Session, tmp_path: Path) -> None:
    resume = _make_resume(tmp_path)
    service = _service(db_session)
    service.import_resume(resume)

    p = db_session.scalar(select(Profile).limit(1))
    assert p is not None
    assert p.active is True

    name = service.activate_profile(p.id)
    assert name is not None

    db_session.expire_all()
    p2 = db_session.scalar(select(Profile).limit(1))
    assert p2 is not None
    assert p2.active is True


def test_resume_import_completeness(db_session: Session, tmp_path: Path) -> None:
    resume = _make_resume(tmp_path)
    service = _service(db_session)
    service.import_resume(resume)
    comp = service.get_completeness()
    assert comp.score > 50.0
    assert "awards" not in comp.missing_fields
    assert "projects" not in comp.missing_fields


def test_profile_export_contains_personal_info(db_session: Session, tmp_path: Path) -> None:
    resume = _make_resume(tmp_path)
    service = _service(db_session)
    service.import_resume(resume)
    output = tmp_path / "export.json"
    service.export_profile(output)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "personal_info" in content
    assert "completeness_score" in content
    assert "John Doe" in content


def test_validate_profile_after_import(db_session: Session, tmp_path: Path) -> None:
    resume = _make_resume(tmp_path)
    service = _service(db_session)
    service.import_resume(resume)
    errors = service.validate_profile()
    assert errors == []


def test_list_versions_after_single_import(db_session: Session, tmp_path: Path) -> None:
    resume = _make_resume(tmp_path)
    service = _service(db_session)
    service.import_resume(resume)
    versions = service.list_versions()
    assert len(versions) >= 1
    assert versions[0].version_number >= 1


def test_profile_list_and_activate(db_session: Session, tmp_path: Path) -> None:
    service = _service(db_session)
    resume = _make_resume(tmp_path)
    service.import_resume(resume)

    profiles = service.list_profiles()
    assert len(profiles) == 1
    assert profiles[0]["active"] is True

    name = service.activate_profile(profiles[0]["id"])
    assert name is not None


def test_delete_profile(db_session: Session, tmp_path: Path) -> None:
    service = _service(db_session)
    resume = _make_resume(tmp_path)
    service.import_resume(resume)
    pid = service.list_profiles()[0]["id"]
    service.delete_profile(pid)
    assert db_session.query(Profile).count() == 0


def test_delete_nonexistent_profile(db_session: Session) -> None:
    import pytest

    service = _service(db_session)
    with pytest.raises(ProfileNotFoundError):
        service.delete_profile(999)


def test_edit_profile_name(db_session: Session, tmp_path: Path) -> None:
    service = _service(db_session)
    resume = _make_resume(tmp_path)
    service.import_resume(resume)
    pid = service.list_profiles()[0]["id"]
    service.edit_profile(profile_id=pid, name="Renamed")
    db_session.expire_all()
    row = db_session.scalar(select(Profile).where(Profile.id == pid))
    assert row is not None
    assert row.name == "Renamed"


def test_edit_profile_summary_creates_version(db_session: Session, tmp_path: Path) -> None:
    service = _service(db_session)
    resume = _make_resume(tmp_path)
    service.import_resume(resume)
    pid = service.list_profiles()[0]["id"]
    service.edit_profile(profile_id=pid, summary="New summary")
    versions = db_session.query(ProfileVersionRecord).filter_by(profile_id=pid).all()
    assert len(versions) == 2
    assert versions[1].version_number == 2


def test_pipeline_orchestrator_uses_active_profile(db_session: Session, tmp_path: Path) -> None:
    resume = _make_resume(tmp_path)
    service = _service(db_session)
    service.import_resume(resume)

    profile = service.get_current_profile()
    assert profile.personal_info.full_name == "John Doe"

    orchestrator = PipelineOrchestrator(session=db_session)
    with (
        patch(
            "app.services.pipeline_orchestrator.DiscoveryService.run_once",
        ) as mock_discovery,
        patch(
            "app.services.pipeline_orchestrator.RecommendationService.recommend",
            return_value=[],
        ),
    ):
        mock_discovery.return_value = type(
            "DR",
            (),
            {
                "fetched_count": 0,
                "duplicate_count": 0,
                "semantic_duplicates": 0,
            },
        )()
        result = orchestrator.run()
    assert result.run_id is not None
    assert isinstance(result.jobs_found, int)
