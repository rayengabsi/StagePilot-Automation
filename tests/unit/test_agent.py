from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agent.agent import CareerAgent
from app.domain.master_profile.entities import MasterProfile, PersonalInfo, Skill
from app.domain.master_profile.errors import ProfileNotFoundError
from app.domain.recommendation.entities import (
    HardRuleResult,
    MatchedDetail,
    Recommendation,
    RecommendationInsights,
    ScoreBreakdown,
)
from app.domain.recommendation.enums import ConfidenceLevel, RecommendationStatus
from app.services.discovery_service import DiscoverySummary
from app.services.pipeline_orchestrator import PipelineRunResult


def _fake_session() -> MagicMock:
    session = MagicMock()
    session.scalar.return_value = None
    session.get.return_value = None
    session.commit.return_value = None
    return session


def _agent(session: MagicMock | None = None, services: dict | None = None) -> CareerAgent:
    return CareerAgent(session=session or _fake_session(), services=services or {})


def _active_profile() -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(
            full_name="Rayen Ben Ahmed",
            email="rayen@example.com",
            location="Tunis",
        ),
        skills=(Skill(name="Python"), Skill(name="AWS")),
    )


def _recommendation() -> Recommendation:
    return Recommendation(
        profile_id=1,
        job_id=7,
        final_score=88.0,
        ranking_position=1,
        status=RecommendationStatus.ACTIVE,
        matched_detail=MatchedDetail(matched_skills=("Python",)),
        score_breakdown=ScoreBreakdown(skills=100.0),
        hard_rule_result=HardRuleResult(passed=True),
        insights=RecommendationInsights(
            confidence=ConfidenceLevel.HIGH, summary="Strong Python match"
        ),
    )


class _FakeDiscovery:
    def __init__(self, summary: DiscoverySummary) -> None:
        self.summary = summary
        self.backfill: bool | None = None

    def run_once(self, backfill_existing: bool = False) -> DiscoverySummary:
        self.backfill = backfill_existing
        return self.summary


class _FakeRecommendation:
    def __init__(self, recommendations: list[Recommendation]) -> None:
        self.recommendations = recommendations
        self.recommend_top: int | None = None
        self.list_top: int | None = None

    def recommend(self, top_n: int | None = None) -> list[Recommendation]:
        self.recommend_top = top_n
        return self.recommendations

    def list_recommendations(self, top_n: int | None = None) -> list[Recommendation]:
        self.list_top = top_n
        return self.recommendations


def test_help_returns_capabilities() -> None:
    response = _agent().handle("help")
    assert response.success
    assert response.intent.value == "help"
    assert "Career Agent" in response.message
    assert response.data["capabilities"]


def test_unknown_message_is_failure() -> None:
    response = _agent().handle("the sky is blue")
    assert not response.success
    assert response.intent.value == "unknown"
    assert "discover jobs" in response.message


def test_profile_status() -> None:
    completeness = SimpleNamespace(
        score=82.5, breakdown={"skills": 100.0}, missing_fields=["certifications"]
    )
    fake = SimpleNamespace(
        get_current_profile=lambda: _active_profile(),
        get_completeness=lambda: completeness,
    )
    response = _agent(services={"profile": fake}).handle("show profile")
    assert response.success
    assert response.intent.value == "profile_status"
    assert "82" in response.message
    assert response.data["counts"]["skills"] == 2
    assert response.data["completeness_score"] == 82.5


def test_profile_status_no_profile_offers_hint() -> None:
    fake = SimpleNamespace(
        get_current_profile=MagicMock(side_effect=ProfileNotFoundError("No active profile found.")),
    )
    response = _agent(services={"profile": fake}).handle("show profile")
    assert not response.success
    assert "No career profile is available yet" in response.message


def test_discover_runs_without_backfill() -> None:
    summary = DiscoverySummary(
        run_id="run-1",
        sources_count=3,
        fetched_count=5,
        inserted_count=5,
        duplicate_count=1,
        invalid_count=0,
        failed_sources_count=0,
        accepted=4,
        rejected=1,
        semantic_duplicates=2,
        rejection_breakdown={},
        duplicate_strategy_breakdown={},
        duration_seconds=2.5,
    )
    fake = _FakeDiscovery(summary)
    response = _agent(services={"discovery": fake}).handle("discover jobs")
    assert response.success
    assert fake.backfill is False
    assert response.data["fetched_count"] == 5
    assert "Discovery finished" in response.message


def test_discover_honors_backfill_flag() -> None:
    summary = DiscoverySummary(
        run_id="run-1",
        sources_count=1,
        fetched_count=0,
        inserted_count=0,
        duplicate_count=0,
        invalid_count=0,
        failed_sources_count=0,
        accepted=0,
        rejected=0,
        semantic_duplicates=0,
        rejection_breakdown={},
        duplicate_strategy_breakdown={},
        duration_seconds=0.1,
    )
    fake = _FakeDiscovery(summary)
    _agent(services={"discovery": fake}).handle("discover jobs with backfill")
    assert fake.backfill is True


def test_recommend_top_n_and_data() -> None:
    fake = _FakeRecommendation([_recommendation()])
    response = _agent(services={"recommendation": fake}).handle("recommend top 5")
    assert response.success
    assert fake.recommend_top == 5
    assert response.data[0]["job_id"] == 7
    assert "88" in response.message


def test_recommend_empty() -> None:
    fake = _FakeRecommendation([])
    response = _agent(services={"recommendation": fake}).handle("recommend")
    assert response.success
    assert "no recommendations" in response.message.lower()


def test_list_recommendations() -> None:
    fake = _FakeRecommendation([_recommendation()])
    response = _agent(services={"recommendation": fake}).handle("list recommendations")
    assert response.success
    assert fake.list_top is None
    assert response.intent.value == "list_recommendations"


def test_explain_without_id_is_error() -> None:
    response = _agent().handle("explain")
    assert not response.success
    assert "Which recommendation" in response.message


def test_explain_missing_recommendation() -> None:
    fake = _FakeRecommendation([])
    response = _agent(services={"recommendation": fake}).handle("explain job 99")
    assert not response.success
    assert "no recommendation for job" in response.message.lower()


def test_explain_returns_explanation() -> None:
    fake = _FakeRecommendation([_recommendation()])
    explanation = SimpleNamespace(
        explanation="Because you know Python.",
        to_dict=lambda: {"explanation": "Because you know Python."},
    )
    fake_explain = SimpleNamespace(explain=lambda *_args, **_kwargs: explanation)
    services = {"recommendation": fake, "explanation": fake_explain}
    response = _agent(services=services).handle("explain job 7")
    assert response.success
    assert response.data["job_id"] == 7
    assert response.message == "Because you know Python."


def test_pipeline_run() -> None:
    result = PipelineRunResult(
        run_id=9,
        jobs_found=4,
        matched=3,
        ai_completed=2,
        ai_failed=0,
        packages_created=2,
        queued=2,
        duration_seconds=1.2,
        errors=[],
    )
    fake = SimpleNamespace(run=lambda: result)
    response = _agent(services={"pipeline": fake}).handle("run the pipeline")
    assert response.success
    assert "Pipeline run #9" in response.message
    assert response.data["matched"] == 3


def test_application_analytics() -> None:
    analytics: dict = {
        "counts": {"submitted": 4, "interview": 2, "offer": 1, "rejected": 0},
        "rates": {"interview_rate": 50.0, "offer_rate": 25.0},
    }
    fake = SimpleNamespace(analytics=lambda: analytics, summarize=lambda: {"total": 4})
    response = _agent(services={"application": fake}).handle("application analytics")
    assert response.success
    assert "4 submitted" in response.message


def test_approval_queue_empty() -> None:
    fake = SimpleNamespace(
        queue_count=lambda: 0,
        peek_queue=lambda **_kwargs: [],
    )
    response = _agent(services={"approval": fake}).handle("approval queue")
    assert response.success
    assert "empty" in response.message


def test_approval_queue_lists_waiting() -> None:
    fake = SimpleNamespace(
        queue_count=lambda: 3,
        peek_queue=lambda **_kwargs: [],
    )
    response = _agent(services={"approval": fake}).handle("approval queue")
    assert response.success
    assert "3 applications" in response.message


def test_profile_edit_name() -> None:
    fake = SimpleNamespace(edit_profile=lambda **_kwargs: None)
    session = _fake_session()
    session.scalar.return_value = 5
    response = _agent(session=session, services={"profile": fake}).handle(
        "edit profile --name 'Rayen'"
    )
    assert response.success
    assert response.data["profile_id"] == 5
    assert response.data["updated"] == {"name": "Rayen"}


def test_response_to_dict_is_serialisable() -> None:
    response = _agent().handle("help")
    payload = response.to_dict()
    assert payload["intent"] == "help"
    assert payload["success"] is True
    assert isinstance(payload["reasoning"], list)
