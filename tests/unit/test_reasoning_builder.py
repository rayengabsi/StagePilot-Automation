from __future__ import annotations

from datetime import date

from app.db.models.jobs import Job
from app.domain.master_profile.entities import (
    Education,
    Experience,
    MasterProfile,
    PersonalInfo,
    Preference,
    Skill,
)
from app.domain.master_profile.enums import RemotePreference
from app.domain.recommendation.entities import HardRuleResult, MatchedDetail, ScoreBreakdown
from app.domain.recommendation.reasoning import ReasoningBuilder


def _profile(
    skills: tuple[Skill, ...] = (),
    experience: tuple[Experience, ...] = (),
    education: tuple[Education, ...] = (),
    location: str | None = None,
    remote: RemotePreference = RemotePreference.ANY,
) -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(full_name="Test", location=location),
        skills=skills,
        experience=experience,
        education=education,
        preferences=Preference(remote_preference=remote),
    )


def _job(
    title: str = "Engineer",
    location: str | None = None,
    description: str = "",
    specialization: str | None = None,
    seniority: str | None = None,
    work_mode: str | None = None,
) -> Job:
    return Job(
        id=1,
        raw_job_id=1,
        source_id=1,
        title=title,
        company="Acme",
        location=location,
        description=description,
        requirements="",
        normalized_hash="abc",
        classification_specialization=specialization,
        classification_seniority=seniority,
        classification_work_mode=work_mode,
    )


def _build(
    profile: MasterProfile,
    job: Job,
    breakdown: ScoreBreakdown | None = None,
    matched: MatchedDetail | None = None,
    hard_rule_result: HardRuleResult | None = None,
) -> tuple[tuple[str, ...], str]:
    return ReasoningBuilder().build(
        profile,
        job,
        breakdown or ScoreBreakdown(),
        matched or MatchedDetail(),
        hard_rule_result,
    )


def test_strong_skills_match_reason() -> None:
    profile = _profile(skills=(Skill(name="Python"), Skill(name="FastAPI")))
    job = _job(description="Python and FastAPI developer")
    reasons, summary = _build(
        profile,
        job,
        ScoreBreakdown(skills=100.0),
        MatchedDetail(matched_skills=("Python", "FastAPI")),
    )
    assert "Strong Python and FastAPI match" in reasons
    assert "Strong Python and FastAPI match" in summary


def test_partial_match_reason() -> None:
    profile = _profile(skills=(Skill(name="Python"),))
    job = _job(description="Python")
    reasons, _ = _build(
        profile,
        job,
        ScoreBreakdown(skills=40.0),
        MatchedDetail(matched_skills=("Python",)),
    )
    assert "Partial Python match" in reasons


def test_missing_technology_experience_reason() -> None:
    reasons, _ = _build(
        _profile(),
        _job(),
        matched=MatchedDetail(missing_technologies=("Docker",)),
    )
    assert "Missing Docker experience" in reasons


def test_missing_skill_reason() -> None:
    reasons, _ = _build(
        _profile(),
        _job(),
        matched=MatchedDetail(missing_skills=("Go",)),
    )
    assert "Missing Go" in reasons


def test_location_mismatch_reason() -> None:
    reasons, _ = _build(
        _profile(location="France"),
        _job(location="Tunisia"),
        ScoreBreakdown(location=0.0),
    )
    assert "Location mismatch" in reasons


def test_location_compatible_reason() -> None:
    reasons, _ = _build(
        _profile(location="France"),
        _job(location="Paris"),
        ScoreBreakdown(location=100.0),
    )
    assert "Location compatible" in reasons


def test_no_location_signal_produces_no_location_reason() -> None:
    reasons, _ = _build(
        _profile(location="France"),
        _job(location=None),
        ScoreBreakdown(location=0.0),
    )
    assert not any("ocation" in reason for reason in reasons)


def test_remote_friendly_reason() -> None:
    reasons, _ = _build(
        _profile(remote=RemotePreference.REMOTE),
        _job(work_mode="remote"),
        ScoreBreakdown(remote=100.0),
    )
    assert "Remote-friendly role" in reasons


def test_onsite_conflict_reason() -> None:
    reasons, _ = _build(
        _profile(remote=RemotePreference.REMOTE),
        _job(work_mode="onsite"),
        ScoreBreakdown(remote=0.0),
    )
    assert "On-site role conflicts with remote preference" in reasons


def test_remote_fallback_from_score_when_unclassified() -> None:
    reasons, _ = _build(
        _profile(remote=RemotePreference.REMOTE),
        _job(work_mode=None),
        ScoreBreakdown(remote=100.0),
    )
    assert "Remote-friendly role" in reasons


def test_seniority_too_ambitious_reason() -> None:
    profile = _profile(
        experience=(
            Experience(company="C1", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)),
        )
    )
    reasons, _ = _build(profile, _job(seniority="senior"))
    assert "Role may exceed current experience level" in reasons


def test_seniority_aligned_reason() -> None:
    profile = _profile(
        experience=(
            Experience(company="C1", start_date=date(2016, 1, 1), end_date=date(2020, 1, 1)),
            Experience(company="C2", start_date=date(2020, 1, 1), end_date=date(2024, 1, 1)),
        )
    )
    reasons, _ = _build(profile, _job(seniority="senior"))
    assert "Seniority aligned" in reasons


def test_seniority_too_junior_reason() -> None:
    profile = _profile(
        experience=(
            Experience(company="C1", start_date=date(2015, 1, 1), end_date=date(2024, 1, 1)),
        )
    )
    reasons, _ = _build(profile, _job(seniority="intern"))
    assert "Role may be below experience level" in reasons


def test_education_aligned_reason() -> None:
    profile = _profile(education=(Education(institution="U", degree="MSc"),))
    reasons, _ = _build(
        profile,
        _job(description="MSc"),
        ScoreBreakdown(education=100.0),
    )
    assert "Education aligns" in reasons


def test_education_mismatch_reason() -> None:
    profile = _profile(education=(Education(institution="U", degree="MSc"),))
    reasons, _ = _build(
        profile,
        _job(),
        ScoreBreakdown(education=0.0),
    )
    assert "Education may not align" in reasons


def test_hard_rule_failure_reasons() -> None:
    hard = HardRuleResult(
        passed=False,
        reasons=("Job location 'Tunisia' does not match preferred countries: France",),
    )
    reasons, summary = _build(
        _profile(),
        _job(),
        hard_rule_result=hard,
    )
    assert any("Job location 'Tunisia' does not match" in r for r in reasons)
    assert summary.endswith(".")


def test_no_signals_summary() -> None:
    _, summary = _build(_profile(), _job())
    assert summary == "No strong signals detected"


def test_summary_joins_reasons() -> None:
    _reasons, summary = _build(
        _profile(skills=(Skill(name="Python"),)),
        _job(location="Tunisia", description="Python"),
        ScoreBreakdown(skills=100.0, location=0.0),
        MatchedDetail(matched_skills=("Python",), missing_technologies=("Docker",)),
    )
    assert summary == "Strong Python match.Missing Docker experience.Location mismatch."
