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


def test_first_import_becomes_active_profile() -> None:
    """The first imported profile must be available as the current profile."""
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    current = service.get_current_profile()
    assert current.personal_info.full_name == "John Doe"
    session.expire_all()
    active = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active) == 1


def test_import_targets_existing_active_profile() -> None:
    """Importing when an active profile exists must update it, not a stale row."""
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    first_id = service.list_profiles()[0]["id"]

    session.add(Profile(active=False, name="Stale"))
    session.add(Profile(active=False, name="Stale 2"))
    session.flush()

    service.import_resume(Path("fake.pdf"))
    session.expire_all()
    active = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active) == 1
    assert active[0].id == first_id
    versions = session.query(ProfileVersionRecord).filter_by(profile_id=first_id).all()
    assert len(versions) == 2


def test_import_activates_when_no_active_profile_exists() -> None:
    """Reproduces the crash: rows exist but none active, then import + completeness."""
    session = _session()
    service = ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("fake.pdf"))
    pid = service.list_profiles()[0]["id"]
    service.delete_profile(pid)

    session.add(Profile(active=False, name="Stale"))
    session.add(Profile(active=False, name="Stale 2"))
    session.flush()

    service.import_resume(Path("fake.pdf"))
    current = service.get_current_profile()
    assert current.personal_info.full_name == "John Doe"
    comp = service.get_completeness()
    assert comp.score > 0
    session.expire_all()
    active = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active) == 1


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


class _MultiEntryFakeParser:
    """Synthetic resume with multiple entries per structured section."""

    def parse(self, _file_path: Path) -> str:
        return """Alex Smith
alex@example.com

Summary
Full-stack engineer with multiple internships.

Education
North Polytechnic
Engineering Degree in Software Engineering Sep. 2020 - Jun. 2024
East High School
High School Diploma Sep. 2016 - Jun. 2020

Experience
Software Engineering Intern Jul. 2024 - Present
Acme Software
Built microservices.
QA Intern Jul. 2023 - Aug. 2023
Bees Inc
Wrote automated tests.

Projects
TradeSim - FastAPI, React
Built a trading simulator.
TripPal - FastAPI, React Native, Firebase
Built a trip planner app.

Skills
Python, Java, Docker, SQL, TypeScript

Languages
Arabic (native)
French (B2)
English (C1)
"""


def _service(session: Session) -> ProfileService:
    return ProfileService(
        session=session,
        parser=_FakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )


# ---------------------------------------------------------------------------
# Single-active invariant regression tests
# ---------------------------------------------------------------------------


def test_activating_one_profile_deactivates_another() -> None:
    """Test A: activating profile B must deactivate the previously active A."""
    session = _session()
    service = _service(session)
    service.import_resume(Path("fake.pdf"))
    profile_a = session.query(Profile).filter(Profile.active.is_(True)).one()
    profile_b = Profile(active=False, name="Candidate B")
    session.add(profile_b)
    session.flush()

    session.query(Profile).filter(Profile.id == profile_a.id).update({"active": True})
    session.commit()

    name = service.activate_profile(profile_b.id)
    assert name is not None
    session.expire_all()
    active_rows = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active_rows) == 1
    assert active_rows[0].id == profile_b.id
    session.expire_all()
    a = session.query(Profile).filter_by(id=profile_a.id).one()
    b = session.query(Profile).filter_by(id=profile_b.id).one()
    assert a.active is False
    assert b.active is True


def test_import_does_not_create_second_active_profile() -> None:
    """Test B: importing must keep exactly one active profile."""
    session = _session()
    service = _service(session)
    service.import_resume(Path("fake.pdf"))
    first_id = service.list_profiles()[0]["id"]

    session.add(Profile(active=False, name="Historical"))
    session.flush()

    service.import_resume(Path("fake.pdf"))
    session.expire_all()
    active_rows = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active_rows) == 1
    assert active_rows[0].id == first_id
    assert session.query(Profile).count() == 2
    remaining = session.query(Profile).filter(Profile.active.is_(False)).all()
    assert len(remaining) == 1
    assert remaining[0].name == "Historical"


def test_legacy_multiple_active_resolves_deterministically() -> None:
    """Test C: corrupted multi-active state must resolve deterministically."""
    session = _session()
    service = _service(session)
    older = Profile(active=True, name="Legacy Older")
    newer = Profile(active=True, name="Legacy Newer")
    session.add_all([older, newer])
    session.flush()

    current = service.get_current_profile()
    assert current.personal_info.full_name == ""
    session.expire_all()
    active_rows = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active_rows) == 1
    assert active_rows[0].id == older.id
    session.expire_all()
    assert session.query(Profile).filter_by(id=newer.id).one().active is False
    assert session.query(Profile).count() == 2


def test_no_profiles_keeps_no_profile_behavior() -> None:
    """Test D: no profiles must surface the existing 'no profile' behavior."""
    import pytest

    session = _session()
    service = _service(session)
    with pytest.raises(ProfileNotFoundError):
        service.get_current_profile()


def test_get_current_profile_returns_active_amid_inactive_history() -> None:
    """Test E: historical inactive profiles must stay untouched and active wins."""
    session = _session()
    service = _service(session)
    session.add_all(
        [
            Profile(active=False, name="Old 1"),
            Profile(active=True, name="Current"),
            Profile(active=False, name="Old 2"),
            Profile(active=False, name="Old 3"),
        ]
    )
    session.flush()
    current = service.get_current_profile()
    assert current.personal_info.full_name == ""
    session.expire_all()
    active_rows = session.query(Profile).filter(Profile.active.is_(True)).all()
    assert len(active_rows) == 1
    assert active_rows[0].name == "Current"
    session.expire_all()
    names = {r.name: r.active for r in session.query(Profile).all()}
    assert names == {
        "Old 1": False,
        "Current": True,
        "Old 2": False,
        "Old 3": False,
    }


def test_import_roundtrip_preserves_multi_entry_data() -> None:
    """Test F: a multi-entry profile must survive import + re-read intact."""
    session = _session()
    service = ProfileService(
        session=session,
        parser=_MultiEntryFakeParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )
    service.import_resume(Path("multi.pdf"))
    current = service.get_current_profile()
    assert len(current.experience) == 2
    assert len(current.education) == 2
    assert len(current.projects) == 2
    assert len(current.languages) == 3
    assert len(current.skills) >= 5
    companies = [e.company for e in current.experience]
    assert "Acme Software" in companies and "Bees Inc" in companies
    institutions = [e.institution for e in current.education]
    assert "North Polytechnic" in institutions and "East High School" in institutions
    project_names = [p.name for p in current.projects]
    assert "TradeSim" in project_names and "TripPal" in project_names
