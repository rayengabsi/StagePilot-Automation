"""Integration tests for PipelineOrchestrator."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.db.models.jobs import Job as JobRecord
from app.db.models.pipeline import PipelineRunRecord
from app.domain.approval.entities import ApplicationPackage
from app.domain.recommendation.entities import (
    HardRuleResult,
    MatchedDetail,
    Recommendation,
    ScoreBreakdown,
)
from app.domain.recommendation.enums import RecommendationStatus
from app.services.pipeline_orchestrator import PipelineOrchestrator
from sqlalchemy.orm import Session


def _fake_recommendation(
    job_id: int,
    final_score: float,
    skills: float = 80.0,
    tech: float = 0.0,
    edu: float = 0.0,
    exp: float = 0.0,
    loc: float = 0.0,
) -> Recommendation:
    return Recommendation(
        profile_id=1,
        job_id=job_id,
        final_score=final_score,
        ranking_position=1,
        status=RecommendationStatus.ACTIVE,
        matched_detail=MatchedDetail(
            matched_skills=("python",),
            missing_skills=(),
        ),
        score_breakdown=ScoreBreakdown(
            skills=skills,
            technologies=tech,
            education=edu,
            experience=exp,
            location=loc,
        ),
        hard_rule_result=HardRuleResult(passed=True),
    )


def _fake_job_record(job_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        title=f"Software Engineer Intern {job_id}",
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
    fetched_count = 10
    duplicate_count = 2
    semantic_duplicates = 1


class TestPipelineOrchestrator:
    def _session_get_side_effect(self, _db_session: Session) -> Any:  # noqa: ANN401
        def _get(model: Any, ident: Any) -> Any:  # noqa: ANN401
            if model is JobRecord:
                return _fake_job_record(ident)
            return None

        return _get

    def _run_pipeline(self, db_session: Session) -> tuple[PipelineOrchestrator, Any]:
        orchestrator = PipelineOrchestrator(session=db_session)
        with (
            patch.object(
                db_session,
                "get",
                side_effect=self._session_get_side_effect(db_session),
            ),
            patch(
                "app.services.pipeline_orchestrator.DiscoveryService.run_once",
            ) as mock_discovery,
            patch(
                "app.services.pipeline_orchestrator.RecommendationService.recommend",
            ) as mock_recommend,
            patch(
                "app.services.pipeline_orchestrator.ProfileService.get_current_profile",
            ) as mock_profile,
            patch(
                "app.services.pipeline_orchestrator.AIOrchestrator._build_provider",
            ),
            patch(
                "app.services.pipeline_orchestrator.AIOrchestrator.generate_text",
                return_value="mock explanation",
            ),
            patch(
                "app.services.pipeline_orchestrator.AIOrchestrator.generate_json",
                return_value={
                    "summary": "Experienced intern",
                    "skills": "Python, SQL",
                    "experience": "Built apps",
                    "projects": "CLI tool",
                },
            ),
            patch(
                "app.services.pipeline_orchestrator.RendererFactory.render_resume",
            ),
            patch(
                "app.services.pipeline_orchestrator.RendererFactory.render_cover_letter",
            ),
            patch(
                "app.services.pipeline_orchestrator.ApprovalService.create_package",
            ) as mock_create_pkg,
            patch(
                "app.services.pipeline_orchestrator.ApprovalService.enqueue",
            ),
        ):
            mock_profile.return_value = _fake_profile()
            mock_discovery.return_value = FakeDiscoveryResult()

            mock_recommend.return_value = [
                _fake_recommendation(1, 75.0, skills=80, loc=60),
                _fake_recommendation(2, 85.0, skills=90, loc=70),
                _fake_recommendation(3, 45.0, skills=50, loc=30),
            ]

            def _create_pkg_side_effect(pkg: ApplicationPackage) -> ApplicationPackage:
                return ApplicationPackage(
                    id=pkg.recommendation_id,
                    recommendation_id=pkg.recommendation_id,
                    job_id=pkg.job_id,
                    profile_id=pkg.profile_id,
                    final_score=pkg.final_score,
                    snapshot_json=pkg.snapshot_json,
                    documents_json=pkg.documents_json,
                    application_hash=pkg.application_hash,
                    profile_version=pkg.profile_version,
                    template_name=pkg.template_name,
                    theme_name=pkg.theme_name,
                    priority=pkg.priority,
                    created_at=datetime.now(UTC),
                )

            mock_create_pkg.side_effect = _create_pkg_side_effect

            result = orchestrator.run()
        return orchestrator, result

    def test_full_successful_pipeline(self, db_session: Session) -> None:
        _, result = self._run_pipeline(db_session)

        assert result.jobs_found == 12
        assert result.duplicates_removed == 3
        assert result.normalized == 10
        assert result.matched == 3
        assert result.below_threshold == 0
        assert result.ai_completed == 3
        assert result.ai_failed == 0
        assert result.rendering_completed == 3
        assert result.packages_created == 3
        assert result.queued == 3
        assert result.duration_seconds > 0
        assert len(result.errors) == 0

    def test_persists_pipeline_run_record(self, db_session: Session) -> None:
        _, result = self._run_pipeline(db_session)
        record = db_session.get(PipelineRunRecord, result.run_id)
        assert record is not None
        assert record.status == "completed"
        assert record.jobs_found == 12
        assert record.queued == 3

    def test_empty_pipeline_no_jobs(self, db_session: Session) -> None:
        orchestrator = PipelineOrchestrator(session=db_session)
        with (
            patch(
                "app.services.pipeline_orchestrator.DiscoveryService.run_once",
                return_value=None,
            ),
            patch(
                "app.services.pipeline_orchestrator.RecommendationService.recommend",
                return_value=[],
            ),
        ):
            result = orchestrator.run()

        assert result.jobs_found == 0
        assert result.matched == 0
        assert result.ai_completed == 0
        assert result.packages_created == 0
        assert result.queued == 0

    def test_discovery_failure_still_continues(self, db_session: Session) -> None:
        orchestrator = PipelineOrchestrator(session=db_session)
        with (
            patch(
                "app.services.pipeline_orchestrator.DiscoveryService.run_once",
                side_effect=RuntimeError("discovery down"),
            ),
            patch(
                "app.services.pipeline_orchestrator.RecommendationService.recommend",
                return_value=[],
            ),
        ):
            result = orchestrator.run()

        assert len(result.errors) >= 1
        assert any(e["step"] == "discovery" for e in result.errors)
        record = db_session.get(PipelineRunRecord, result.run_id)
        assert record.status == "completed"

    def test_partial_ai_failures(self, db_session: Session) -> None:
        """First AI call succeeds, second fails (ResumeTailorService.tailor)."""
        orchestrator = PipelineOrchestrator(session=db_session)
        call_count = 0

        def _json_side_effect(*args: Any, **kwargs: Any) -> dict:  # noqa: ANN401
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("AI model unavailable")
            return {
                "summary": "test",
                "skills": "test",
                "experience": "test",
                "projects": "test",
            }

        with (
            patch.object(
                db_session,
                "get",
                side_effect=self._session_get_side_effect(db_session),
            ),
            patch(
                "app.services.pipeline_orchestrator.DiscoveryService.run_once",
                return_value=FakeDiscoveryResult(),
            ),
            patch(
                "app.services.pipeline_orchestrator.RecommendationService.recommend",
                return_value=[
                    _fake_recommendation(1, 80.0, skills=80, loc=80),
                    _fake_recommendation(2, 90.0, skills=90, loc=80),
                ],
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
                return_value="mock",
            ),
            patch(
                "app.services.pipeline_orchestrator.AIOrchestrator.generate_json",
                side_effect=_json_side_effect,
            ),
            patch(
                "app.services.pipeline_orchestrator.RendererFactory.render_resume",
            ),
            patch(
                "app.services.pipeline_orchestrator.RendererFactory.render_cover_letter",
            ),
            patch(
                "app.services.pipeline_orchestrator.ApprovalService.create_package",
            ),
            patch(
                "app.services.pipeline_orchestrator.ApprovalService.enqueue",
            ),
        ):
            orchestrator.run()

        assert call_count == 2

    def test_pipeline_with_rendering_failures(self, db_session: Session) -> None:
        orchestrator = PipelineOrchestrator(session=db_session)

        with (
            patch.object(
                db_session,
                "get",
                side_effect=self._session_get_side_effect(db_session),
            ),
            patch(
                "app.services.pipeline_orchestrator.DiscoveryService.run_once",
                return_value=FakeDiscoveryResult(),
            ),
            patch(
                "app.services.pipeline_orchestrator.RecommendationService.recommend",
                return_value=[
                    _fake_recommendation(1, 80.0, skills=80, loc=80),
                ],
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
                return_value={
                    "summary": "test",
                    "skills": "test",
                    "experience": "test",
                    "projects": "test",
                },
            ),
            patch(
                "app.services.pipeline_orchestrator.RendererFactory.render_resume",
                side_effect=RuntimeError("PDF error"),
            ),
        ):
            result = orchestrator.run()

        assert result.rendering_failed == 1
        assert result.rendering_completed == 0
        assert result.ai_completed == 1
        assert any(e["step"] == "rendering" for e in result.errors)

    def test_no_profile_loaded(self, db_session: Session) -> None:
        orchestrator = PipelineOrchestrator(session=db_session)

        with (
            patch.object(
                db_session,
                "get",
                side_effect=self._session_get_side_effect(db_session),
            ),
            patch(
                "app.services.pipeline_orchestrator.DiscoveryService.run_once",
                return_value=FakeDiscoveryResult(),
            ),
            patch(
                "app.services.pipeline_orchestrator.RecommendationService.recommend",
                return_value=[
                    _fake_recommendation(1, 80.0, skills=80, loc=80),
                ],
            ),
            patch(
                "app.services.pipeline_orchestrator.ProfileService.get_current_profile",
                return_value=None,
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
                return_value={
                    "summary": "test",
                    "skills": "test",
                    "experience": "test",
                    "projects": "test",
                },
            ),
            patch(
                "app.services.pipeline_orchestrator.RendererFactory.render_resume",
            ),
            patch(
                "app.services.pipeline_orchestrator.RendererFactory.render_cover_letter",
            ),
            patch(
                "app.services.pipeline_orchestrator.ApprovalService.create_package",
            ) as mock_create_pkg,
            patch(
                "app.services.pipeline_orchestrator.ApprovalService.enqueue",
            ),
        ):

            def _create_pkg_side_effect(pkg: ApplicationPackage) -> ApplicationPackage:
                return ApplicationPackage(
                    id=pkg.recommendation_id,
                    recommendation_id=pkg.recommendation_id,
                    job_id=pkg.job_id,
                    profile_id=pkg.profile_id or 0,
                    final_score=pkg.final_score,
                    snapshot_json=pkg.snapshot_json,
                    documents_json=pkg.documents_json,
                    application_hash=pkg.application_hash,
                    profile_version=pkg.profile_version,
                    template_name=pkg.template_name,
                    theme_name=pkg.theme_name,
                    priority=pkg.priority,
                    created_at=datetime.now(UTC),
                )

            mock_create_pkg.side_effect = _create_pkg_side_effect

            result = orchestrator.run()

        assert result.ai_failed == 1
        assert result.ai_completed == 0
