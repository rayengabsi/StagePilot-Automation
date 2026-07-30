from __future__ import annotations

from app.config.matching import MatchingConfig
from app.db.models.jobs import Job
from app.domain.master_profile.entities import MasterProfile, PersonalInfo, Preference
from app.domain.master_profile.enums import RemotePreference
from app.domain.recommendation.matcher import HardRuleMatcher


def _config(**overrides: bool) -> MatchingConfig:
    rules = {
        "match_country": True,
        "match_work_mode": True,
        "match_language": True,
    }
    rules.update(overrides)
    return MatchingConfig(
        weights={},
        thresholds={},
        hard_rules=rules,
        fuzz_threshold=60,
    )


def _profile(prefs: Preference | None = None) -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(full_name="Test"),
        preferences=prefs or Preference(),
    )


def _job(location: str = "", title: str = "", description: str = "", requirements: str = "") -> Job:
    return Job(
        id=1, raw_job_id=1, source_id=1, title=title, company="Acme",
        location=location, description=description, requirements=requirements,
        normalized_hash="abc",
    )


def test_country_match_success() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference(preferred_countries=("Tunisia",)))
    job = _job(location="Tunisia, Tunis")
    result = matcher.evaluate(profile, job)
    assert result.passed
    assert not result.reasons


def test_country_match_failure() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference(preferred_countries=("France",)))
    job = _job(location="Tunisia, Tunis")
    result = matcher.evaluate(profile, job)
    assert not result.passed
    assert any("France" in r for r in result.reasons)


def test_country_match_no_preference_skips() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference())
    job = _job(location="Tunisia")
    result = matcher.evaluate(profile, job)
    assert result.passed


def test_work_mode_remote_success() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference(remote_preference=RemotePreference.REMOTE))
    job = _job(description="This is a remote position")
    result = matcher.evaluate(profile, job)
    assert result.passed


def test_work_mode_remote_failure() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference(remote_preference=RemotePreference.REMOTE))
    job = _job(description="On-site work only")
    result = matcher.evaluate(profile, job)
    assert not result.passed


def test_work_mode_any_skips() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference(remote_preference=RemotePreference.ANY))
    job = _job(description="whatever")
    result = matcher.evaluate(profile, job)
    assert result.passed


def test_language_success() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference(preferred_language="English"))
    job = _job(description="English is required")
    result = matcher.evaluate(profile, job)
    assert result.passed


def test_language_failure() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference(preferred_language="French"))
    job = _job(description="English only")
    result = matcher.evaluate(profile, job)
    assert not result.passed


def test_language_no_preference_skips() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(Preference())
    job = _job(description="whatever")
    result = matcher.evaluate(profile, job)
    assert result.passed


def test_all_hard_rules_disabled() -> None:
    matcher = HardRuleMatcher(
        _config(match_country=False, match_work_mode=False, match_language=False)
    )
    profile = _profile(
        Preference(
            preferred_countries=("Mars",),
            remote_preference=RemotePreference.REMOTE,
        )
    )
    job = _job(location="Tunisia")
    result = matcher.evaluate(profile, job)
    assert result.passed


def test_multiple_reasons() -> None:
    matcher = HardRuleMatcher(_config())
    profile = _profile(
        Preference(
            preferred_countries=("France",),
            remote_preference=RemotePreference.REMOTE,
            preferred_language="French",
        )
    )
    job = _job(location="Tunisia", description="On-site English")
    result = matcher.evaluate(profile, job)
    assert not result.passed
    assert len(result.reasons) >= 1
