from __future__ import annotations

from app.config.matching import MatchingConfig
from app.db.models.jobs import Job
from app.domain.master_profile.entities import (
    Education,
    Experience,
    Language,
    MasterProfile,
    PersonalInfo,
    Preference,
    Project,
    Skill,
)
from app.domain.master_profile.enums import ProficiencyLevel
from app.domain.recommendation.scorer import SimilarityScorer


def _config() -> MatchingConfig:
    return MatchingConfig(
        weights={},
        thresholds={},
        hard_rules={},
        fuzz_threshold=60,
    )


def _job(
    title: str = "Software Engineer",
    location: str = "Tunisia",
    description: str = "Python, FastAPI, SQL",
    requirements: str = "",
) -> Job:
    return Job(
        id=1,
        raw_job_id=1,
        source_id=1,
        title=title,
        company="Acme",
        location=location,
        description=description,
        requirements=requirements,
        normalized_hash="abc",
    )


def _profile(
    skills: tuple[Skill, ...] = (),
    experience: tuple[Experience, ...] = (),
    education: tuple[Education, ...] = (),
    languages: tuple[Language, ...] = (),
    projects: tuple[Project, ...] = (),
    preferences: Preference | None = None,
) -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(full_name="Test", location="Tunisia"),
        skills=skills,
        experience=experience,
        education=education,
        languages=languages,
        projects=projects,
        preferences=preferences or Preference(),
    )


def test_skills_score_all_matched() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(skills=(Skill(name="Python"), Skill(name="SQL")))
    job = _job(description="Python, SQL, FastAPI")
    scores = scorer.score_all(profile, job)
    assert scores.skills == 100.0


def test_skills_score_partial() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(skills=(Skill(name="Python"), Skill(name="Rust"), Skill(name="SQL")))
    job = _job(description="Python, SQL")
    scores = scorer.score_all(profile, job)
    assert 0.0 < scores.skills < 100.0


def test_skills_score_empty() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile()
    job = _job(description="Python")
    scores = scorer.score_all(profile, job)
    assert scores.skills == 0.0


def test_technologies_score() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(
        experience=(Experience(company="C1", technologies=("Docker", "AWS")),),
    )
    job = _job(description="Docker and AWS experience")
    scores = scorer.score_all(profile, job)
    assert scores.technologies == 100.0


def test_technologies_score_partial() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(
        experience=(Experience(company="C1", technologies=("Docker", "Kubernetes")),),
    )
    job = _job(description="Docker experience")
    scores = scorer.score_all(profile, job)
    assert 0.0 < scores.technologies < 100.0


def test_education_score() -> None:
    scorer = SimilarityScorer(_config())
    edu = Education(institution="MIT", degree="BSc", field_of_study="Computer Science")
    profile = _profile(education=(edu,))
    job = _job(description="Computer Science degree required")
    scores = scorer.score_all(profile, job)
    assert scores.education > 0.0


def test_education_score_empty() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile()
    job = _job(description="Computer Science")
    scores = scorer.score_all(profile, job)
    assert scores.education == 0.0


def test_languages_score() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(languages=(Language(name="English", proficiency=ProficiencyLevel.FLUENT),))
    job = _job(description="English required")
    scores = scorer.score_all(profile, job)
    assert scores.languages == 100.0


def test_languages_no_profile_languages() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile()
    job = _job(description="French is a plus")
    scores = scorer.score_all(profile, job)
    assert scores.languages == 50.0


def test_location_match_exact() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(preferences=Preference())
    job = _job(location="Tunisia")
    scores = scorer.score_all(profile, job)
    assert scores.location == 100.0


def test_location_no_job_location() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile()
    job = _job(location="")
    scores = scorer.score_all(profile, job)
    assert scores.location == 50.0


def test_preferences_score() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(
        preferences=Preference(
            preferred_technologies=("Python", "FastAPI"),
        ),
    )
    job = _job(description="Python and FastAPI developers wanted")
    scores = scorer.score_all(profile, job)
    assert scores.preferences == 100.0


def test_preferences_score_partial() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(
        preferences=Preference(
            preferred_technologies=("Python", "TensorFlow"),
        ),
    )
    job = _job(description="Python developers wanted")
    scores = scorer.score_all(profile, job)
    assert 0.0 < scores.preferences < 100.0


def test_match_detail_returns_matched_and_missing() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(
        skills=(Skill(name="Python"), Skill(name="Rust")),
        preferences=Preference(preferred_technologies=("Docker",)),
    )
    job = _job(description="Python developers, Docker experience")
    detail = scorer.match_detail(profile, job)
    assert "Python" in detail.matched_skills
    assert "Rust" in detail.missing_skills
    assert "Docker" in detail.matched_preferences


def test_projects_score() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(projects=(Project(name="React Dashboard"),))
    job = _job(description="React Dashboard")
    scores = scorer.score_all(profile, job)
    assert scores.projects > 0.0


def test_experience_score() -> None:
    scorer = SimilarityScorer(_config())
    profile = _profile(experience=(Experience(company="Google", title="Software Engineer"),))
    job = _job(title="Software Engineer at Google")
    scores = scorer.score_all(profile, job)
    assert scores.experience > 0.0
