from __future__ import annotations

from pathlib import Path

from app.db.base import Base
from app.db.models.profile import (
    CertificationRecord,
    EducationRecord,
    ExperienceRecord,
    LanguageRecord,
    Profile,
    ProfileVersionRecord,
    SkillRecord,
)
from app.domain.master_profile.entities import MasterProfile
from app.domain.master_profile.errors import ProfileNotFoundError
from app.services.profile_normalizer import ProfileNormalizer
from app.services.profile_service import ProfileService
from app.services.profile_validator import ProfileValidator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class _FakeParser:
    def parse(self, _file_path: Path) -> str:
        return """John Doe
john@example.com
https://github.com/johndoe

Education
University of Tunis
Master in Computer Science
2020 2024

Experience
Tech Corp
Software Engineer Intern
2023 2024

Skills
Python, Java, Docker, SQL, Kubernetes

Languages
English (fluent), French (native)

Certifications
AWS Certified Solutions Architect
"""
        # No projects for this fake resume


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_import_creates_profile_and_version() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    profile = service.import_resume(Path("fake.pdf"))
    assert isinstance(profile, MasterProfile)
    assert profile.personal_info.full_name == "John Doe"
    profile_row = session.query(Profile).first()
    assert profile_row is not None
    versions = session.query(ProfileVersionRecord).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1


def test_import_creates_normalized_tables() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    assert session.query(EducationRecord).count() >= 1
    assert session.query(ExperienceRecord).count() >= 1
    assert session.query(SkillRecord).count() >= 1
    assert session.query(LanguageRecord).count() >= 1
    assert session.query(CertificationRecord).count() >= 1
    assert session.query(Profile).count() == 1


def test_multiple_imports_increment_version() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    service.import_resume(Path("fake.pdf"))
    versions = session.query(ProfileVersionRecord).all()
    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[1].version_number == 2


def test_get_current_profile_raises_if_none() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    import pytest

    with pytest.raises(ProfileNotFoundError):
        service.get_current_profile()


def test_import_replaces_previous_records() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    assert session.query(EducationRecord).count() == 1
    service.import_resume(Path("fake.pdf"))
    assert session.query(EducationRecord).count() == 1


def test_get_completeness_after_import() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    comp = service.get_completeness()
    assert comp.score > 0
    assert "projects" in comp.missing_fields


def test_export_creates_json_file(tmp_path: Path) -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    output = tmp_path / "profile.json"
    service.export_profile(output)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "personal_info" in content
    assert "completeness_score" in content


def test_list_versions_after_import() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    versions = service.list_versions()
    assert len(versions) == 1
    assert versions[0].version_number == 1


def test_list_profiles_after_import() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    profiles = service.list_profiles()
    assert len(profiles) == 1
    p = profiles[0]
    assert p["id"] == 1
    assert p["active"] is True
    assert p["full_name"] == "John Doe"


def test_list_profiles_empty() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    profiles = service.list_profiles()
    assert profiles == ()


def test_activate_profile_switches_active_flag() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    service.import_resume(Path("fake2.pdf"))
    profiles_before = service.list_profiles()
    assert len(profiles_before) == 1  # same profile, just updated

    session.add(Profile(active=False))
    session.add(Profile(active=False))
    session.flush()
    all_rows = session.query(Profile).all()
    assert len(all_rows) >= 2

    name = service.activate_profile(all_rows[1].id)
    assert name is not None
    session.expire_all()
    active_rows = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active_rows) == 1
    assert active_rows[0].id == all_rows[1].id


def test_activate_profile_raises_if_not_found() -> None:
    import pytest

    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    with pytest.raises(ProfileNotFoundError):
        service.activate_profile(999)


def test_delete_profile_removes_row() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    profiles = service.list_profiles()
    assert len(profiles) == 1
    service.delete_profile(profiles[0]["id"])
    assert session.query(Profile).count() == 0


def test_delete_profile_raises_if_not_found() -> None:
    import pytest

    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    with pytest.raises(ProfileNotFoundError):
        service.delete_profile(999)


def test_edit_profile_name() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    profiles = service.list_profiles()
    pid = profiles[0]["id"]
    service.edit_profile(profile_id=pid, name="My Custom Name")
    session.expire_all()
    row = session.query(Profile).filter_by(id=pid).first()
    assert row is not None
    assert row.name == "My Custom Name"


def test_edit_profile_summary_creates_version() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    profiles = service.list_profiles()
    pid = profiles[0]["id"]
    new_summary = "Updated professional summary."
    service.edit_profile(profile_id=pid, summary=new_summary)
    versions = session.query(ProfileVersionRecord).filter_by(profile_id=pid).all()
    assert len(versions) == 2
    assert versions[1].version_number == 2


def test_edit_profile_raises_if_not_found() -> None:
    import pytest

    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    with pytest.raises(ProfileNotFoundError):
        service.edit_profile(profile_id=999, name="test")


def test_validate_profile_on_current() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    errors = service.validate_profile()
    assert isinstance(errors, list)


def test_validate_profile_by_id() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    pid = service.list_profiles()[0]["id"]
    errors = service.validate_profile(profile_id=pid)
    assert isinstance(errors, list)


def test_get_profile_by_id() -> None:
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    pid = service.list_profiles()[0]["id"]
    profile = service.get_profile_by_id(pid)
    assert profile.personal_info.full_name == "John Doe"


def test_get_profile_by_id_raises_if_not_found() -> None:
    import pytest

    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    with pytest.raises(ProfileNotFoundError):
        service.get_profile_by_id(999)
