from __future__ import annotations

from datetime import date

from app.config.matching import MatchingConfig
from app.db.models.jobs import Job
from app.domain.master_profile.entities import (
    Experience,
    MasterProfile,
    PersonalInfo,
    Preference,
    Skill,
)
from app.domain.master_profile.enums import RemotePreference
from app.domain.recommendation.scorer import SimilarityScorer


def _config() -> MatchingConfig:
    return MatchingConfig(weights={}, thresholds={}, hard_rules={}, fuzz_threshold=60)


def _profile(
    skills: tuple[Skill, ...] = (),
    experience: tuple[Experience, ...] = (),
    remote: RemotePreference = RemotePreference.ANY,
) -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(full_name="Test", location="Paris"),
        skills=skills,
        experience=experience,
        preferences=Preference(remote_preference=remote),
    )


def _job(
    title: str = "Engineer",
    description: str = "",
    specialization: str | None = None,
    seniority: str | None = None,
    work_mode: str | None = None,
    location: str | None = None,
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


def test_classification_matches_profile_technology() -> None:
    profile = _profile(skills=(Skill(name="Python"), Skill(name="FastAPI")))
    job = _job(specialization="backend")
    scorer = SimilarityScorer(_config())
    assert scorer._score_classification(profile, job) == 100.0


def test_classification_no_match_is_low() -> None:
    profile = _profile(skills=(Skill(name="React"),))
    job = _job(specialization="backend")
    scorer = SimilarityScorer(_config())
    assert scorer._score_classification(profile, job) == 40.0


def test_classification_no_specialization_is_neutral() -> None:
    profile = _profile(skills=(Skill(name="Python"),))
    job = _job(specialization=None)
    scorer = SimilarityScorer(_config())
    assert scorer._score_classification(profile, job) == 50.0


def test_remote_preference_remote_remote_job() -> None:
    profile = _profile(remote=RemotePreference.REMOTE)
    job = _job(work_mode="remote")
    scorer = SimilarityScorer(_config())
    assert scorer._score_remote(profile, job) == 100.0


def test_remote_preference_remote_onsite_job() -> None:
    profile = _profile(remote=RemotePreference.REMOTE)
    job = _job(work_mode="onsite")
    scorer = SimilarityScorer(_config())
    assert scorer._score_remote(profile, job) == 0.0


def test_remote_preference_any_is_neutral() -> None:
    profile = _profile(remote=RemotePreference.ANY)
    job = _job(work_mode="onsite")
    scorer = SimilarityScorer(_config())
    assert scorer._score_remote(profile, job) == 100.0


def test_remote_detected_from_text_when_unclassified() -> None:
    profile = _profile(remote=RemotePreference.REMOTE)
    job = _job(work_mode=None, description="Remote position")
    scorer = SimilarityScorer(_config())
    assert scorer._score_remote(profile, job) == 100.0


def test_seniority_intern_fits_entry_level() -> None:
    profile = _profile()
    job = _job(seniority="intern")
    scorer = SimilarityScorer(_config())
    assert scorer._score_seniority(profile, job) == 100.0


def test_seniority_senior_underqualified() -> None:
    profile = _profile(
        experience=(
            Experience(company="C1", start_date=date(2023, 1, 1), end_date=date(2024, 1, 1)),
        )
    )
    job = _job(seniority="senior")
    scorer = SimilarityScorer(_config())
    assert scorer._score_seniority(profile, job) == 30.0


def test_seniority_mid_aligned() -> None:
    profile = _profile(
        experience=(
            Experience(company="C1", start_date=date(2019, 1, 1), end_date=date(2024, 1, 1)),
        )
    )
    job = _job(seniority="mid")
    scorer = SimilarityScorer(_config())
    assert scorer._score_seniority(profile, job) == 100.0


def test_seniority_no_signal_neutral() -> None:
    profile = _profile()
    job = _job(seniority=None)
    scorer = SimilarityScorer(_config())
    assert scorer._score_seniority(profile, job) == 50.0


def test_score_all_includes_intelligence_components() -> None:
    profile = _profile(skills=(Skill(name="Python"),))
    job = _job(description="Python developer")
    scorer = SimilarityScorer(_config())
    breakdown = scorer.score_all(profile, job)
    assert breakdown.hard_filters == 100.0
    assert breakdown.ai == 0.0
    assert 0.0 <= breakdown.classification <= 100.0
    assert 0.0 <= breakdown.remote <= 100.0
    assert 0.0 <= breakdown.seniority <= 100.0
