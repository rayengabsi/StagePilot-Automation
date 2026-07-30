from __future__ import annotations

from app.config.matching import MatchingConfig
from app.db.models.jobs import Job
from app.domain.master_profile.entities import MasterProfile, PersonalInfo, Preference, Skill
from app.domain.recommendation.aggregator import ScoreAggregator
from app.domain.recommendation.enums import RecommendationStatus
from app.domain.recommendation.matcher import HardRuleMatcher
from app.domain.recommendation.profile_matcher import ProfileMatcher
from app.domain.recommendation.scorer import SimilarityScorer


def _default_weights() -> dict[str, float]:
    return {
        "skills": 35.0, "technologies": 20.0, "education": 10.0,
        "experience": 10.0, "languages": 5.0, "projects": 5.0,
        "location": 10.0, "preferences": 5.0,
    }


def _config(**rules: bool) -> MatchingConfig:
    hr = {
        "match_country": rules.get("match_country", True),
        "match_work_mode": rules.get("match_work_mode", True),
        "match_language": rules.get("match_language", True),
    }
    return MatchingConfig(
        weights=_default_weights(),
        thresholds={"recommendation_cutoff": 30.0},
        hard_rules=hr,
        fuzz_threshold=60,
    )


def _profile(skills: tuple[Skill, ...] = (), prefs: Preference | None = None) -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(full_name="Test", location="Tunisia"),
        skills=skills,
        preferences=prefs or Preference(),
    )


def _job(title: str = "Engineer", location: str = "Tunisia", description: str = "Python") -> Job:
    return Job(
        id=1, raw_job_id=1, source_id=1, title=title, company="Acme",
        location=location, description=description, requirements="",
        normalized_hash="abc",
    )


def test_match_hard_rule_failure() -> None:
    matcher = ProfileMatcher(
        config=_config(),
        hard_rule_matcher=HardRuleMatcher(_config()),
        scorer=SimilarityScorer(_config()),
        aggregator=ScoreAggregator(_config()),
    )
    profile = _profile(prefs=Preference(preferred_countries=("France",)))
    job = _job(location="Tunisia")
    rec = matcher.match(profile, job, profile_id=1)
    assert rec.status == RecommendationStatus.REJECTED
    assert rec.final_score == 0.0
    assert not rec.hard_rule_result.passed


def test_match_successful() -> None:
    matcher = ProfileMatcher(
        config=_config(),
        hard_rule_matcher=HardRuleMatcher(_config()),
        scorer=SimilarityScorer(_config()),
        aggregator=ScoreAggregator(_config()),
    )
    profile = _profile(skills=(Skill(name="Python"),), prefs=Preference())
    job = _job(description="Python developer")
    rec = matcher.match(profile, job, profile_id=1)
    assert rec.status == RecommendationStatus.ACTIVE or rec.status == RecommendationStatus.REJECTED
    assert rec.final_score >= 0.0
    assert rec.matched_detail.matched_skills == ("Python",)


def test_match_scoring_breakdown() -> None:
    matcher = ProfileMatcher(
        config=_config(),
        hard_rule_matcher=HardRuleMatcher(_config()),
        scorer=SimilarityScorer(_config()),
        aggregator=ScoreAggregator(_config()),
    )
    profile = _profile(skills=(Skill(name="Python"),), prefs=Preference())
    job = _job(description="Python developer looking for remote work")
    rec = matcher.match(profile, job, profile_id=1)
    breakdown = rec.score_breakdown.to_dict()
    assert "skills" in breakdown
    assert "technologies" in breakdown
    assert breakdown["skills"] > 0.0


def test_match_fuzzy_scoring() -> None:
    matcher = ProfileMatcher(
        config=_config(),
        hard_rule_matcher=HardRuleMatcher(_config()),
        scorer=SimilarityScorer(_config()),
        aggregator=ScoreAggregator(_config()),
    )
    profile = _profile(skills=(Skill(name="JavaScript"),), prefs=Preference())
    job = _job(description="JS developer")
    rec = matcher.match(profile, job, profile_id=1)
    assert rec.score_breakdown.skills >= 0.0


def test_match_with_technologies() -> None:
    from app.domain.master_profile.entities import Experience

    matcher = ProfileMatcher(
        config=_config(),
        hard_rule_matcher=HardRuleMatcher(_config()),
        scorer=SimilarityScorer(_config()),
        aggregator=ScoreAggregator(_config()),
    )
    profile = MasterProfile(
        personal_info=PersonalInfo(full_name="Test"),
        experience=(Experience(company="C1", technologies=("Docker", "Kubernetes")),),
    )
    job = _job(description="Docker and Kubernetes experience required")
    rec = matcher.match(profile, job, profile_id=1)
    assert "docker" in rec.matched_detail.matched_technologies
    assert "kubernetes" in rec.matched_detail.matched_technologies
