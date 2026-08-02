from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.approval_config import ApprovalConfig, get_approval_config
from app.config.settings import Settings, get_settings
from app.db.models.jobs import Job as JobRecord
from app.db.models.pipeline import PipelineRunRecord
from app.domain.approval.package import (
    build_documents_json,
    build_snapshot,
    create_application_package,
)
from app.domain.recommendation.entities import Recommendation
from app.infrastructure.job_sources.registry import build_connector_registry
from app.infrastructure.parsers.pdf_parser import PDFParser
from app.rendering.models import CoverLetterData
from app.rendering.renderer_factory import RendererFactory
from app.services.ai_orchestrator import AIOrchestrator
from app.services.approval_service import ApprovalService
from app.services.cover_letter_service import CoverLetterService
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.explanation_service import ExplanationService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.profile_normalizer import ProfileNormalizer
from app.services.profile_service import ProfileService
from app.services.profile_validator import ProfileValidator
from app.services.recommendation_service import RecommendationService
from app.services.resume_tailor_service import ResumeTailorService


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    run_id: int = 0
    jobs_found: int = 0
    duplicates_removed: int = 0
    normalized: int = 0
    matched: int = 0
    below_threshold: int = 0
    ai_completed: int = 0
    ai_failed: int = 0
    rendering_completed: int = 0
    rendering_failed: int = 0
    packages_created: int = 0
    queued: int = 0
    telegram_sent: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0


class PipelineOrchestrator:
    """Coordinates all completed phases into a single pipeline run.

    Executes: discovery → normalization → dedup → filtering → matching
    → AI (explain + tailor + cover letter) → rendering → package → queue → notify.

    Failures in one job never stop the pipeline. All errors are collected.
    """

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        approval_config: ApprovalConfig | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._approval_config = approval_config or get_approval_config()

    def run(self) -> PipelineRunResult:
        started_at = time.time()
        record = PipelineRunRecord(status="running")
        self._session.add(record)
        self._session.flush()

        errors: list[dict[str, Any]] = []

        # Step 1-4: Discovery + normalization + dedup + filtering
        discovery_result = self._run_discovery(errors)
        if discovery_result:
            jobs_found = discovery_result.fetched_count + discovery_result.duplicate_count
            normalized = discovery_result.fetched_count
            duplicates_removed = (
                discovery_result.duplicate_count + discovery_result.semantic_duplicates
            )
        else:
            jobs_found = 0
            normalized = 0
            duplicates_removed = 0

        # Step 5: Profile matching
        recommendations = self._run_matching(errors)
        matched = len(recommendations)

        recommendations_above = [r for r in recommendations if r.final_score > 0]
        below_threshold = matched - len(recommendations_above)

        # Steps 6-9: AI + rendering + package + queue per recommendation
        ai_ok = 0
        ai_fail = 0
        render_ok = 0
        render_fail = 0
        packages_created = 0
        queued = 0
        profile = self._load_profile()
        queue_strategy = self._approval_config.queue_strategy

        for rec in recommendations_above:
            job_row = self._session.get(JobRecord, rec.job_id)
            if not job_row:
                continue

            # Step 6: AI (explain + tailor + cover letter)
            ai_result = self._run_ai_for_job(profile, rec, job_row, errors)
            if ai_result is None:
                ai_fail += 1
                continue
            ai_ok += 1
            explanation_text, tailored, cover_letter_body = ai_result

            # Step 7: Rendering
            render_paths = self._run_rendering(
                profile, rec, job_row, tailored, cover_letter_body, errors
            )
            if render_paths is None:
                render_fail += 1
                continue
            render_ok += 1
            pdf_paths, docx_paths = render_paths

            # Step 8: Create ApplicationPackage
            recommendation_data = self._build_recommendation_data(rec, job_row)
            email_draft = {
                "subject": f"Application for {job_row.title} at {job_row.company or 'Company'}",
                "body": cover_letter_body,
            }
            snapshot_json = build_snapshot(
                recommendation_data=recommendation_data,
                profile_data=profile.to_dict() if profile else {},
                explanation=explanation_text,
                tailored_resume={"sections": tailored.sections} if tailored else None,
                cover_letter_body=cover_letter_body,
                email_draft=email_draft,
                pdf_paths=[str(p) for p in pdf_paths],
                docx_paths=[str(p) for p in docx_paths],
                template_name="modern",
                theme_name="default",
            )
            documents_json = build_documents_json(
                resume_pdf=str(pdf_paths[0]) if pdf_paths else "",
                resume_docx=str(docx_paths[0]) if docx_paths else "",
                cover_letter_pdf=str(pdf_paths[1]) if len(pdf_paths) > 1 else "",
                cover_letter_docx=str(docx_paths[1]) if len(docx_paths) > 1 else "",
                email_subject=email_draft["subject"],
                email_body=email_draft["body"],
            )

            package = create_application_package(
                recommendation_id=rec.job_id,
                job_id=rec.job_id,
                profile_id=profile.id if profile else 0,
                final_score=rec.final_score,
                snapshot_json=snapshot_json,
                documents_json=documents_json,
                template_name="modern",
                theme_name="default",
                priority=int(rec.final_score),
            )

            # Step 9: Save and enqueue
            try:
                approval_svc = ApprovalService(
                    self._session,
                    queue_strategy=queue_strategy,
                )
                saved = approval_svc.create_package(package)
                approval_svc.enqueue(saved.id, score=rec.final_score)
                packages_created += 1
                queued += 1
            except Exception as exc:
                errors.append(
                    {
                        "step": "enqueue",
                        "job_id": rec.job_id,
                        "error": str(exc),
                    }
                )

        # Step 10: Telegram notification
        telegram_sent = self._notify_telegram(queued, errors)

        duration = time.time() - started_at

        # Update pipeline run record
        record.status = "completed"
        record.finished_at = self._now()
        record.duration_seconds = duration
        record.jobs_found = jobs_found
        record.duplicates_removed = duplicates_removed
        record.normalized = normalized
        record.matched = matched
        record.below_threshold = below_threshold
        record.ai_completed = ai_ok
        record.ai_failed = ai_fail
        record.rendering_completed = render_ok
        record.rendering_failed = render_fail
        record.packages_created = packages_created
        record.queued = queued
        record.telegram_sent = telegram_sent
        record.error_summary_json = errors[:50] if errors else None

        self._session.flush()

        return PipelineRunResult(
            run_id=record.id,
            jobs_found=jobs_found,
            duplicates_removed=duplicates_removed,
            normalized=normalized,
            matched=matched,
            below_threshold=below_threshold,
            ai_completed=ai_ok,
            ai_failed=ai_fail,
            rendering_completed=render_ok,
            rendering_failed=render_fail,
            packages_created=packages_created,
            queued=queued,
            telegram_sent=telegram_sent,
            errors=errors,
            duration_seconds=duration,
        )

    def _run_discovery(self, errors: list[dict[str, Any]]) -> Any | None:  # noqa: ANN401
        try:
            registry = build_connector_registry(self._settings)
            filter_service = HardFilterService(self._settings.filter_rules)
            duplicate_service = DuplicateDetectionService(
                self._session,
                fuzzy_threshold=self._settings.filter_rules.fuzzy_title_threshold,
            )
            matching_service = JobMatchingService(self._session, filter_service, duplicate_service)
            discovery = DiscoveryService(
                session=self._session,
                connector_registry=registry,
                normalizer=JobNormalizationService(),
                matching_service=matching_service,
            )
            return discovery.run_once()
        except Exception as exc:
            errors.append({"step": "discovery", "error": str(exc)})
            return None

    def _run_matching(self, errors: list[dict[str, Any]]) -> list[Recommendation]:
        try:
            rec_service = RecommendationService(session=self._session)
            return rec_service.recommend()
        except Exception as exc:
            errors.append({"step": "matching", "error": str(exc)})
            return []

    def _load_profile(self) -> Any | None:  # noqa: ANN401
        try:
            profile_service = ProfileService(
                session=self._session,
                parser=PDFParser(),
                normalizer=ProfileNormalizer(),
                validator=ProfileValidator(),
            )
            return profile_service.get_current_profile()
        except Exception:
            return None

    def _run_ai_for_job(
        self,
        profile: Any,  # noqa: ANN401
        rec: Recommendation,
        job_row: JobRecord,
        errors: list[dict[str, Any]],
    ) -> tuple[str, Any, str] | None:
        try:
            orchestrator = AIOrchestrator(
                ai_config=None,  # type: ignore[arg-type]
                settings=self._settings,
                session=self._session,
            )
            explanation_svc = ExplanationService(orchestrator=orchestrator)
            tailor_svc = ResumeTailorService(orchestrator=orchestrator)
            cover_svc = CoverLetterService(orchestrator=orchestrator)

            explanation = explanation_svc.explain(
                rec,
                job_title=job_row.title or "",
                company=job_row.company or "",
            )
            tailored = tailor_svc.tailor(
                profile,
                rec,
                job_description=job_row.description or "",
            )
            cover = cover_svc.generate(
                profile,
                rec,
                company=job_row.company or "",
            )
            return explanation.explanation, tailored, cover.body
        except Exception as exc:
            errors.append(
                {
                    "step": "ai",
                    "job_id": rec.job_id,
                    "error": str(exc),
                }
            )
            return None

    def _run_rendering(
        self,
        profile: Any,  # noqa: ANN401
        rec: Recommendation,
        job_row: JobRecord,  # noqa: ARG002
        tailored: Any,  # noqa: ANN401
        cover_letter_body: str,
        errors: list[dict[str, Any]],
    ) -> tuple[list[Path], list[Path]] | None:
        try:
            output_dir = Path("output") / f"job_{rec.job_id}"
            output_dir.mkdir(parents=True, exist_ok=True)

            factory = RendererFactory()

            resume_pdf = output_dir / "resume.pdf"
            resume_docx = output_dir / "resume.docx"
            cover_pdf = output_dir / "cover_letter.pdf"
            cover_docx = output_dir / "cover_letter.docx"

            tailored_sections = tailored.sections if tailored else None

            factory.render_resume(
                profile,
                resume_pdf,
                template_name="modern",
                tailored_sections=tailored_sections,
                fmt="pdf",
            )
            factory.render_resume(
                profile,
                resume_docx,
                template_name="modern",
                tailored_sections=tailored_sections,
                fmt="docx",
            )

            cover_data = CoverLetterData(
                body=cover_letter_body,
                candidate_name=profile.personal_info.full_name if profile else "Candidate",
            )
            factory.render_cover_letter(
                profile, cover_data, cover_pdf, template_name="modern", fmt="pdf"
            )
            factory.render_cover_letter(
                profile, cover_data, cover_docx, template_name="modern", fmt="docx"
            )

            return [resume_pdf, cover_pdf], [resume_docx, cover_docx]
        except Exception as exc:
            errors.append(
                {
                    "step": "rendering",
                    "job_id": rec.job_id,
                    "error": str(exc),
                }
            )
            return None

    def _build_recommendation_data(self, rec: Recommendation, job_row: JobRecord) -> dict[str, Any]:
        return {
            "job": {
                "id": rec.job_id,
                "title": job_row.title or "",
                "company": job_row.company or "",
                "location": job_row.location or "",
                "description_preview": (job_row.description or "")[:500],
            },
            "final_score": rec.final_score,
            "matched_skills": list(rec.matched_detail.matched_skills),
            "missing_skills": list(rec.matched_detail.missing_skills),
            "score_breakdown": (
                rec.score_breakdown.to_dict() if hasattr(rec.score_breakdown, "to_dict") else {}
            ),
        }

    def _notify_telegram(self, queued_count: int, errors: list) -> bool:
        try:
            from app.infrastructure.telegram.notification import TelegramNotificationService

            svc = TelegramNotificationService()
            svc.send_pipeline_summary(queued_count, len(errors))
            return True
        except Exception:
            return False

    def _now(self) -> Any:  # noqa: ANN401
        from datetime import UTC, datetime

        return datetime.now(UTC)
