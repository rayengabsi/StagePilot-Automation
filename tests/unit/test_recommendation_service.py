from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.config.matching import MatchingConfig
from app.db.models.profile import Profile as ProfileRecord
from app.domain.master_profile.entities import MasterProfile, PersonalInfo, Skill
from app.domain.recommendation.enums import FeedbackReason
from app.domain.recommendation.errors import ProfileNotReadyError


def _matching_config() -> MatchingConfig:
    return MatchingConfig(
        weights={
            "skills": 35.0,
            "technologies": 20.0,
            "education": 10.0,
            "experience": 10.0,
            "languages": 5.0,
            "projects": 5.0,
            "location": 10.0,
            "preferences": 5.0,
        },
        thresholds={"recommendation_cutoff": 0.0},
        hard_rules={
            "match_country": True,
            "match_work_mode": True,
            "match_language": True,
        },
        fuzz_threshold=60,
    )


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.query.return_value = session.query
    session.filter.return_value = session.filter
    session.order_by.return_value = session.order_by
    session.limit.return_value = session.limit
    session.all.return_value = []
    session.add.return_value = None
    session.flush.return_value = None
    return session


@pytest.fixture
def config() -> MatchingConfig:
    return _matching_config()


def _make_profile_record(record_id: int = 1) -> ProfileRecord:
    rec = ProfileRecord()
    rec.id = record_id
    return rec


@patch("app.services.profile_service.ProfileService")
def test_recommend_no_profile(
    mock_ps_cls: MagicMock, mock_session: MagicMock, config: MatchingConfig
) -> None:
    mock_instance = MagicMock()
    mock_instance.get_current_profile.side_effect = ProfileNotReadyError("no profile")
    mock_ps_cls.return_value = mock_instance

    from app.services.recommendation_service import RecommendationService

    service = RecommendationService(session=mock_session, config=config)
    with pytest.raises(ProfileNotReadyError):
        service.recommend()


@patch("app.services.profile_service.ProfileService")
def test_recommend_empty_jobs(
    mock_ps_cls: MagicMock, mock_session: MagicMock, config: MatchingConfig
) -> None:
    from app.services.recommendation_service import RecommendationService

    mock_instance = MagicMock()
    mock_instance.get_current_profile.return_value = MasterProfile(
        personal_info=PersonalInfo(full_name="Test"),
        skills=(Skill(name="Python"),),
    )
    mock_ps_cls.return_value = mock_instance
    mock_session.scalar.return_value = _make_profile_record(1)
    mock_session.execute.return_value.scalars.return_value.all.return_value = []

    service = RecommendationService(session=mock_session, config=config)
    results = service.recommend()
    assert results == []


@patch("app.services.profile_service.ProfileService")
def test_feedback_creates_record(
    mock_ps_cls: MagicMock, mock_session: MagicMock, config: MatchingConfig
) -> None:
    from app.services.recommendation_service import RecommendationService

    mock_instance = MagicMock()
    mock_instance.get_current_profile.return_value = MasterProfile(
        personal_info=PersonalInfo(full_name="Test"),
    )
    mock_ps_cls.return_value = mock_instance
    mock_session.scalar.return_value = _make_profile_record(1)
    mock_session.execute.return_value.scalars.return_value.all.return_value = []

    service = RecommendationService(session=mock_session, config=config)
    fb = service.feedback(recommendation_id=1, reason="wrong_country", comment="Bad location")
    assert fb.recommendation_id == 1
    assert fb.reason == FeedbackReason.WRONG_COUNTRY
    assert fb.comment == "Bad location"


@patch("app.services.profile_service.ProfileService")
def test_list_recommendations_empty(
    _mock_ps_cls: MagicMock, mock_session: MagicMock, config: MatchingConfig
) -> None:
    from app.services.recommendation_service import RecommendationService

    mock_session.query.return_value.order_by.return_value.all.return_value = []
    service = RecommendationService(session=mock_session, config=config)
    results = service.list_recommendations()
    assert results == []


@patch("app.services.profile_service.ProfileService")
@patch("app.services.recommendation_service.select")
def test_recommend_with_jobs(
    _mock_select: MagicMock,
    _mock_ps_cls: MagicMock,
    mock_session: MagicMock,
    config: MatchingConfig,
) -> None:
    from app.services.recommendation_service import RecommendationService

    mock_instance = MagicMock()
    mock_instance.get_current_profile.return_value = MasterProfile(
        personal_info=PersonalInfo(full_name="Test"),
        skills=(Skill(name="Python"),),
    )
    mock_session.scalar.return_value = _make_profile_record(1)
    mock_session.execute.return_value.scalars.return_value.all.return_value = []

    service = RecommendationService(session=mock_session, config=config)
    results = service.recommend()
    assert results == []
