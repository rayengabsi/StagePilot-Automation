"""Integration tests for the AI Tailoring Quality Layer in the pipeline."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.db.models.jobs import Job as JobRecord
from app.domain.approval.enums import ApprovalState
from app.domain.recommendation.entities import (
    HardRuleResult,
    MatchedDetail,
    Recommendation,
    ScoreBreakdown,
)
from app.domain.recommendation.enums import RecommendationStatus
from app.services.pipeline_orchestrator import PipelineOrchestrator
from sqlalchemy.orm import Session


def _fake_recommendation(job_id: int, final_score: float = 80.0) -> Recommendation:
    return Recommendation(
        profile_id=1,
        job_id=job_id,
        final_score=final_score,
        ranking_position=1,
        status=RecommendationStatus.ACTIVE,
        matched_detail=MatchedDetail(matched_skills=("python",)),
        score_breakdown=ScoreBreakdown(skills=80.0),
        hard_rule_result=HardRuleResult(passed=True),
    )


def _fake_job_record(job_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        title="Software Engineer",
        company="Tech Corp",
        location="Remote",
        description="Python, SQL, teamwork",
    )


def _fake_profile() -> SimpleNamespace:
    return SimpleNamespace(
        personal_info=SimpleNamespace(full_name="Test User"),
        education=[],
        experience=[],
        id=1,
        to_dict=lambda: {"name": "Test User"},
    )


class FakeDiscoveryResult:
    fetched_count = 5
    duplicate_count = 1
    semantic_duplicates = 0


GOOD_RESUME = {
    "summary": "Backend engineer specializing in Python and FastAPI APIs.",
    "skills": "Python, SQL",
    "experience": "Built REST APIs with FastAPI.",
    "projects": "Built a data pipeline with Docker.",
}

HALLUCINATED_RESUME = {
    "summary": "Worked at Google on Kubernetes infrastructure.",
    "skills": "Hadoop, Kafka",
    "experience": "Held a PhD from Harvard.",
    "projects": "TODO: add project details",
}


def _session_get_side_effect(_session: Session) -> Any:  # noqa: ANN401
    def _get(model: Any, ident: Any) -> Any:  # noqa: ANN401
        if model is JobRecord:
            return _fake_job_record(ident)
        return None

    return _get


def _run_pipeline(
    db_session: Session,
    resume_json: dict[str, str],
    *,
    create_package_side_effect: Any = None,  # noqa: ANN401
    capture_enqueue: list | None = None,
) -> tuple[PipelineOrchestrator, Any]:
    captured: list[tuple[Any, ...]] = capture_enqueue if capture_enqueue is not None else []

    def _record_enqueue(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        captured.append(args)

    orchestrator = PipelineOrchestrator(session=db_session)
    with (
        patch.object(db_session, "get", side_effect=_session_get_side_effect(db_session)),
        patch(
            "app.services.pipeline_orchestrator.DiscoveryService.run_once",
            return_value=FakeDiscoveryResult(),
        ),
        patch(
            "app.services.pipeline_orchestrator.RecommendationService.recommend",
            return_value=[_fake_recommendation(1, 80.0)],
        ),
        patch(
            "app.services.pipeline_orchestrator.ProfileService.get_current_profile",
            return_value=_fake_profile(),
        ),
        patch(
            "app.services.pipeline_orchestrator.AIOrchestrator._build_provider",
        ),
        patch(
            "app.services.pipeline_orchestrator.AIOrchestrator.generate_text",
            return_value="mock explanation",
        ),
        patch(
            "app.services.pipeline_orchestrator.AIOrchestrator.generate_json",
            return_value=resume_json,
        ),
        patch(
            "app.services.pipeline_orchestrator.RendererFactory.render_resume",
        ),
        patch(
            "app.services.pipeline_orchestrator.RendererFactory.render_cover_letter",
        ),
        patch(
            "app.services.pipeline_orchestrator.ApprovalService.create_package",
            side_effect=create_package_side_effect,
        ) as mock_create,
        patch(
            "app.services.pipeline_orchestrator.ApprovalService.enqueue",
            side_effect=_record_enqueue,
        ),
    ):
        result = orchestrator.run()
    return result, mock_create


def _create_package_stub(package: Any) -> Any:  # noqa: ANN401
    return SimpleNamespace(id=package.recommendation_id)


def test_good_quality_resume_is_enqueued(db_session: Session) -> None:
    captured: list[Any] = []
    result, mock_create = _run_pipeline(
        db_session,
        GOOD_RESUME,
        create_package_side_effect=_create_package_stub,
        capture_enqueue=captured,
    )

    assert result.ai_completed == 1
    assert result.needs_revision == 0
    assert result.rendering_completed == 1
    assert result.queued == 1
    assert len(captured) == 1

    pkg = mock_create.call_args.args[0]
    snapshot = json.loads(pkg.snapshot_json)
    assert "quality" in snapshot
    assert snapshot["quality"]["resume"]["needs_revision"] is False


def test_hallucinated_resume_is_marked_for_revision(db_session: Session) -> None:
    captured: list[Any] = []
    result, mock_create = _run_pipeline(
        db_session,
        HALLUCINATED_RESUME,
        create_package_side_effect=_create_package_stub,
        capture_enqueue=captured,
    )

    assert result.ai_completed == 1
    assert result.needs_revision == 1
    assert result.rendering_completed == 0
    assert result.queued == 0
    assert len(captured) == 0

    pkg = mock_create.call_args.args[0]
    assert pkg.status == ApprovalState.REVISION_REQUESTED
    snapshot = json.loads(pkg.snapshot_json)
    assert snapshot["quality"]["resume"]["needs_revision"] is True
    assert snapshot["quality"]["resume"]["overall_quality"] == "needs_revision"


def test_quality_disabled_never_marks_revision(db_session: Session) -> None:
    from app.config.ai_config import get_ai_config

    original = get_ai_config()
    disabled = _with_quality(original, enabled=False)
    with (
        patch("app.services.pipeline_orchestrator.get_ai_config", return_value=disabled),
        patch("app.services.ai_tailoring_evaluator.get_ai_config", return_value=disabled),
    ):
        result, _ = _run_pipeline(
            db_session,
            HALLUCINATED_RESUME,
            create_package_side_effect=_create_package_stub,
        )

    assert result.needs_revision == 0
    assert result.queued == 1


def _with_quality(config: Any, *, enabled: bool) -> Any:  # noqa: ANN401
    from app.config.ai_config import AIConfig, TailoringQualityConfig

    return AIConfig(
        provider=config.provider,
        features=config.features,
        tailoring_quality=TailoringQualityConfig(
            enabled=enabled,
            minimum_quality_score=config.tailoring_quality.minimum_quality_score,
        ),
    )
