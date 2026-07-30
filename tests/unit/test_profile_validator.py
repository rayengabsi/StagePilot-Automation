from __future__ import annotations

from datetime import date

from app.domain.master_profile.entities import (
    Certification,
    Education,
    Experience,
    Language,
    MasterProfile,
    PersonalInfo,
    Preference,
    Project,
    Skill,
)
from app.services.profile_validator import ProfileValidator


def _make_profile(
    personal_info: PersonalInfo | None = None,
    education: tuple[Education, ...] = (),
    experience: tuple[Experience, ...] = (),
    projects: tuple[Project, ...] = (),
    skills: tuple[Skill, ...] = (),
    languages: tuple[Language, ...] = (),
    certifications: tuple[Certification, ...] = (),
) -> MasterProfile:
    return MasterProfile(
        personal_info=personal_info or PersonalInfo(full_name="Test User"),
        education=education,
        experience=experience,
        projects=projects,
        skills=skills,
        languages=languages,
        certifications=certifications,
        preferences=Preference(),
    )


def test_validator_passes_valid_profile() -> None:
    v = ProfileValidator()
    profile = _make_profile()
    errors = v.validate(profile)
    assert len(errors) == 0


def test_validator_rejects_empty_name() -> None:
    v = ProfileValidator()
    profile = _make_profile(personal_info=PersonalInfo(full_name=""))
    errors = v.validate(profile)
    assert any(e.field == "personal_info.full_name" for e in errors)


def test_validator_rejects_invalid_email() -> None:
    v = ProfileValidator()
    profile = _make_profile(personal_info=PersonalInfo(full_name="Test", email="not-an-email"))
    errors = v.validate(profile)
    assert any(e.field == "personal_info.email" for e in errors)


def test_validator_accepts_valid_email() -> None:
    v = ProfileValidator()
    profile = _make_profile(personal_info=PersonalInfo(full_name="Test", email="test@example.com"))
    errors = v.validate(profile)
    assert not any(e.field == "personal_info.email" for e in errors)


def test_validator_rejects_duplicate_education() -> None:
    v = ProfileValidator()
    profile = _make_profile(
        education=(
            Education(institution="University A", degree="BS", field_of_study="CS"),
            Education(institution="University A", degree="BS", field_of_study="CS"),
        )
    )
    errors = v.validate(profile)
    assert any("Duplicate" in e.message for e in errors)


def test_validator_rejects_invalid_date_range() -> None:
    v = ProfileValidator()
    profile = _make_profile(
        education=(
            Education(
                institution="University A",
                start_date=date(2024, 1, 1),
                end_date=date(2020, 1, 1),
            ),
        )
    )
    errors = v.validate(profile)
    assert any("Start date is after end date" in e.message for e in errors)


def test_validator_rejects_duplicate_skills() -> None:
    v = ProfileValidator()
    profile = _make_profile(
        skills=(
            Skill(name="Python"),
            Skill(name="Python"),
        )
    )
    errors = v.validate(profile)
    assert any("Duplicate" in e.message for e in errors)


def test_completeness_empty_profile() -> None:
    v = ProfileValidator()
    profile = _make_profile(
        personal_info=PersonalInfo(full_name=""),
    )
    comp = v.compute_completeness(profile)
    assert comp.score < 50.0
    assert len(comp.missing_fields) >= 3


def test_completeness_full_profile() -> None:
    v = ProfileValidator()
    profile = _make_profile(
        personal_info=PersonalInfo(
            full_name="Test User",
            email="test@example.com",
            phone="+216 99 123 456",
            linkedin_url="https://linkedin.com/in/test",
            github_url="https://github.com/test",
            portfolio_url="https://test.dev",
        ),
        education=(Education(institution="University A"),),
        skills=(
            Skill(name="Python"),
            Skill(name="Java"),
            Skill(name="SQL"),
            Skill(name="Docker"),
            Skill(name="Kubernetes"),
        ),
        experience=(Experience(company="Company A"),),
        projects=(Project(name="Project X"),),
        certifications=(Certification(name="AWS Certified"),),
        languages=(Language(name="English"),),
    )
    comp = v.compute_completeness(profile)
    assert comp.score > 80.0


def test_completeness_reports_missing_fields() -> None:
    v = ProfileValidator()
    profile = _make_profile()
    comp = v.compute_completeness(profile)
    assert "education" in comp.missing_fields
    assert "skills" in comp.missing_fields
    assert "experience" in comp.missing_fields


def test_validator_rejects_duplicate_certifications() -> None:
    v = ProfileValidator()
    profile = _make_profile(
        certifications=(
            Certification(name="AWS Certified"),
            Certification(name="AWS Certified"),
        )
    )
    errors = v.validate(profile)
    assert any("Duplicate" in e.message for e in errors)


def test_validator_rejects_duplicate_languages() -> None:
    v = ProfileValidator()
    profile = _make_profile(
        languages=(
            Language(name="English"),
            Language(name="English"),
        )
    )
    errors = v.validate(profile)
    assert any("Duplicate" in e.message for e in errors)
