"""The StagePilot Career Agent (Phase 1).

``CareerAgent`` is the first class of the StagePilot v2 agent layer. It does
not implement new business logic: it orchestrates the existing StagePilot
services (profile, discovery, matching, recommendation, AI explanation,
pipeline, application, approval) and explains what it did and why.

Design rules for this phase:

- The existing deterministic pipeline is untouched. The agent only composes it.
- Every action produces ``reasoning`` so the user always sees the agent's
  explanation before/after the result.
- Intent classification is deterministic and testable. An LLM refinement of
  intent handling is deferred to a later phase.
- Services are injected lazily through a lightweight registry, which keeps the
  class testable without a database.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.intents import AgentIntent, IntentClassifier
from app.agent.responses import AgentResponse
from app.config.ai_config import get_ai_config
from app.config.settings import Settings, get_settings
from app.db.models.jobs import Job as JobRecord
from app.db.models.profile import Profile as ProfileRecord
from app.domain.ai.errors import ProviderError
from app.domain.master_profile.errors import ProfileNotFoundError, ProfileValidationError
from app.infrastructure.job_sources.registry import build_connector_registry
from app.infrastructure.parsers.parser_factory import detect_parser
from app.infrastructure.parsers.pdf_parser import PDFParser
from app.services.ai_orchestrator import AIOrchestrator
from app.services.application_service import ApplicationService
from app.services.approval_service import ApprovalService
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.explanation_service import ExplanationService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.profile_normalizer import ProfileNormalizer
from app.services.profile_service import ProfileService
from app.services.profile_validator import ProfileValidator
from app.services.recommendation_service import RecommendationService
from app.utils import pii as pii_utils

_ABS_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"']+")
_REL_PATH_RE = re.compile(r"(?:\.{1,2}[\\/]|~[\\/])[^\s\"']+")
_EXT_PATH_RE = re.compile(r"[^\s\"']+\.(?:pdf|docx|md)(?:[\\/][^\s\"']*)?", re.IGNORECASE)
_TOP_FLAG_RE = re.compile(r"--top\s+(\d+)", re.IGNORECASE)
_TOP_PHRASE_RE = re.compile(r"\b(?:top|first)\s+(\d+)\b", re.IGNORECASE)
_TRAILING_N_RE = re.compile(
    r"\s(\d{1,2})\s*(?:recommendations?|jobs|matches|results)?\s*$", re.IGNORECASE
)
_LABELED_ID_RE = re.compile(r"(?:recommendation|rec|job|id)\s*#?\s*(\d{1,7})\b", re.IGNORECASE)
_FIRST_INT_RE = re.compile(r"\b(\d{1,7})\b")
_NAME_FLAG_RE = re.compile(r"--name\s+[\"']?([^\"']+?)[\"']?(?=\s+--|\s*$)")
_SUMMARY_FLAG_RE = re.compile(r"--summary\s+[\"']?([^\"']+?)[\"']?(?=\s+--|\s*$)")
_SUMMARY_TO_RE = re.compile(
    r"(?:set|update)\s+(?:my\s+)?summary\s+to\s+[\"']?([^\"']+)[\"']?\s*$", re.IGNORECASE
)


class CareerAgent:
    """Orchestrate the existing StagePilot services behind a conversational interface.

    The agent receives a free-text message, classifies the intent, executes the
    matching capability through the existing services, and answers with a
    human-friendly message plus structured data and reasoning.
    """

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        services: dict[str, Any] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._classifier = IntentClassifier()
        #: Lightweight service registry; entries can be injected in tests.
        self._services: dict[str, Any] = services or {}

    #  Public entry point

    def handle(self, message: str) -> AgentResponse:
        """Process one user message and return the agent's answer."""
        intent = self._classifier.classify(message)
        dispatcher = self._dispatchers().get(intent)
        if dispatcher is None:
            return self._respond_unknown(intent, message)

        try:
            return dispatcher(message)
        except ProfileNotFoundError as exc:
            return self._error_response(
                intent,
                message,
                exc,
                hint="No career profile is available yet. Import a resume first, e.g. "
                "`import resume path/to/resume.pdf`.",
            )
        except ProfileValidationError as exc:
            return self._error_response(
                intent, message, exc, hint=f"Profile validation failed: {exc}"
            )
        except ProviderError as exc:
            return self._error_response(
                intent,
                message,
                exc,
                hint="AI features need a configured LLM API key in your `.env` file.",
            )
        except Exception as exc:
            return self._error_response(intent, message, exc)

    #  Intent dispatch

    def _dispatchers(self) -> dict[AgentIntent, Callable[[str], AgentResponse]]:
        return {
            AgentIntent.UNKNOWN: self._unknown,
            AgentIntent.HELP: self._help,
            AgentIntent.PROFILE_STATUS: self._profile_status,
            AgentIntent.PROFILE_IMPORT: self._profile_import,
            AgentIntent.PROFILE_EDIT: self._profile_edit,
            AgentIntent.DISCOVER: self._discover,
            AgentIntent.RECOMMEND: self._recommend,
            AgentIntent.LIST_RECOMMENDATIONS: self._list_recommendations,
            AgentIntent.AI_EXPLAIN: self._ai_explain,
            AgentIntent.PIPELINE: self._pipeline,
            AgentIntent.APPLICATION_ANALYTICS: self._application_analytics,
            AgentIntent.APPROVAL_QUEUE: self._approval_queue,
        }

    def _unknown(self, _message: str) -> AgentResponse:
        reasoning = ("I could not map your message to a known capability.",)
        data = {
            "capabilities": self._capability_catalog(),
        }
        return AgentResponse(
            intent=AgentIntent.UNKNOWN,
            message=(
                "I'm not sure what you'd like me to do. "
                "Try one of these: `discover jobs`, `recommend top 5`, "
                "`show profile`, `pipeline`, `approval queue`, or `help`."
            ),
            data=data,
            reasoning=reasoning,
            success=False,
        )

    def _help(self, _message: str) -> AgentResponse:
        reasoning = ("Listed the capabilities I can orchestrate for you.",)
        return AgentResponse(
            intent=AgentIntent.HELP,
            message=(
                "I am your Career Agent. I orchestrate the StagePilot pipeline:\n"
                "- `import resume <path>`  build your career profile from a PDF/DOCX/MD\n"
                "- `show profile`  summarize your stored career profile\n"
                "- `discover jobs`  fetch new job postings from all sources\n"
                "- `recommend top N`  rank jobs against your profile\n"
                "- `explain job <id>`  get an AI explanation of a recommendation\n"
                "- `pipeline`  run the full pipeline (discovery to approval queue)\n"
                "- `applications`  application analytics and outcomes\n"
                "- `approval queue`  applications waiting for your approval"
            ),
            data={"capabilities": self._capability_catalog()},
            reasoning=reasoning,
        )

    def _capability_catalog(self) -> list[dict[str, str]]:
        return [
            {"intent": "profile_import", "example": "import resume path/to/resume.pdf"},
            {"intent": "profile_status", "example": "show profile"},
            {"intent": "profile_edit", "example": "edit profile --summary 'Backend engineer'"},
            {"intent": "discover", "example": "discover jobs"},
            {"intent": "recommend", "example": "recommend top 5"},
            {"intent": "list_recommendations", "example": "list recommendations"},
            {"intent": "ai_explain", "example": "explain job 42"},
            {"intent": "pipeline", "example": "pipeline"},
            {"intent": "application_analytics", "example": "applications"},
            {"intent": "approval_queue", "example": "approval queue"},
        ]

    #  Capabilities

    def _profile_status(self, _message: str) -> AgentResponse:
        service = self._get_service("profile", self._build_profile_service)
        profile = service.get_current_profile()
        completeness = service.get_completeness()

        profile_data = profile.to_dict()
        profile_data["personal_info"] = pii_utils.mask_profile_dict(profile_data["personal_info"])
        data: dict[str, Any] = {
            "full_name": profile.personal_info.full_name,
            "location": profile.personal_info.location,
            "email": pii_utils.mask_value("email", profile.personal_info.email),
            "skills": [s.name for s in profile.skills][:30],
            "counts": {
                "skills": len(profile.skills),
                "experience": len(profile.experience),
                "education": len(profile.education),
                "projects": len(profile.projects),
                "languages": len(profile.languages),
                "certifications": len(profile.certifications),
            },
            "completeness_score": completeness.score,
            "completeness_breakdown": completeness.breakdown,
            "missing_fields": list(completeness.missing_fields),
            "profile": profile_data,
        }
        reasoning = (
            "Loaded your career profile from the master profile store.",
            "Computed completeness and missing fields deterministically.",
        )
        message_text = (
            f"I loaded your career profile{self._display_name(profile.personal_info.full_name)}. "
            f"It contains {len(profile.skills)} skills, {len(profile.experience)} experiences, "
            f"{len(profile.education)} education entries and {len(profile.projects)} projects. "
            f"Completeness is {completeness.score:.0f}%."
        )
        if completeness.missing_fields:
            message_text += (
                f" To improve it, consider adding: {', '.join(completeness.missing_fields)}."
            )
        return self._ok(AgentIntent.PROFILE_STATUS, message_text, data, reasoning)

    def _profile_import(self, message: str) -> AgentResponse:
        path = self._extract_path(message)
        if path is None:
            return self._error(
                AgentIntent.PROFILE_IMPORT,
                "I could not find a resume file path (PDF, DOCX or Markdown) in your message. "
                "Try: `import resume path/to/resume.pdf`.",
                reasoning=("Attempted to import a resume but no file path was detected.",),
            )

        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            return self._error(
                AgentIntent.PROFILE_IMPORT,
                f"I could not access the file at `{path}`. Check that the path is correct.",
                reasoning=(f"Looked for the resume at `{path}` but the file does not exist.",),
            )

        service = ProfileService(
            session=self._session,
            parser=detect_parser(path),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        profile = service.import_resume(file_path, description="Imported via CareerAgent")
        completeness = service.get_completeness()

        data: dict[str, Any] = {
            "status": "imported",
            "path": str(file_path),
            "full_name": profile.personal_info.full_name,
            "counts": {
                "skills": len(profile.skills),
                "experience": len(profile.experience),
                "education": len(profile.education),
                "projects": len(profile.projects),
            },
            "completeness_score": completeness.score,
            "missing_fields": list(completeness.missing_fields),
        }
        reasoning = (
            f"Parsed and normalized the resume from `{path}`.",
            f"Extracted {len(profile.skills)} skills, {len(profile.experience)} experiences and "
            f"{len(profile.education)} education entries.",
            "Validated the profile and saved a new version.",
        )
        message_text = (
            f"Imported your resume from `{path}`. Your career profile now has "
            f"{len(profile.skills)} skills, {len(profile.experience)} experiences, "
            f"{len(profile.education)} education entries and {len(profile.projects)} projects. "
            f"Profile completeness is {completeness.score:.0f}%."
        )
        return self._ok(AgentIntent.PROFILE_IMPORT, message_text, data, reasoning)

    def _profile_edit(self, message: str) -> AgentResponse:
        name = self._extract_flag(message, _NAME_FLAG_RE)
        summary = self._extract_flag(message, _SUMMARY_FLAG_RE)
        if summary is None:
            summary = self._extract_summary_to(message)
        if name is None and summary is None:
            return self._error(
                AgentIntent.PROFILE_EDIT,
                "Tell me what to change, for example: "
                "`edit profile --name 'Rayen Ben Ahmed' --summary 'Backend engineer'`.",
                reasoning=("No editable field was detected in the message.",),
            )

        active_id = self._session.scalar(
            select(ProfileRecord.id).where(ProfileRecord.active.is_(True)).limit(1)
        )
        if active_id is None:
            return self._error(
                AgentIntent.PROFILE_EDIT,
                "There is no profile to edit yet. Import a resume first.",
                reasoning=("Checked for an active profile but none exists.",),
            )

        service = self._get_service("profile", self._build_profile_service)
        service.edit_profile(profile_id=active_id, name=name, summary=summary)

        updated = {key: value for key, value in (("name", name), ("summary", summary)) if value}
        data: dict[str, Any] = {"profile_id": active_id, "updated": updated}
        reasoning = (
            "Located your active profile.",
            f"Updated {', '.join(updated) or 'profile'} and stored a new version.",
        )
        message_text = f"I updated your profile{self._list_updates(updated)}."
        return self._ok(AgentIntent.PROFILE_EDIT, message_text, data, reasoning)

    def _discover(self, message: str) -> AgentResponse:
        backfill = "backfill" in message.lower()
        service = self._get_service("discovery", self._build_discovery_service)
        summary = service.run_once(backfill_existing=backfill)
        data = asdict(summary)

        duplicates = summary.duplicate_count + summary.semantic_duplicates
        reasoning = (
            f"Ran job discovery against {summary.sources_count} configured sources.",
            f"Fetched {summary.fetched_count} postings; skipped {summary.duplicate_count} exact "
            f"and {summary.semantic_duplicates} semantic duplicates.",
            f"{summary.accepted} jobs passed screening, {summary.rejected} were filtered out.",
        )
        message_text = (
            f"Discovery finished in {summary.duration_seconds:.1f}s. I fetched "
            f"{summary.fetched_count} jobs, accepted {summary.accepted} and removed {duplicates} "
            f"duplicates."
        )
        return self._ok(AgentIntent.DISCOVER, message_text, data, reasoning)

    def _recommend(self, message: str) -> AgentResponse:
        top_n = self._extract_top_n(message)
        recommendations = self._recommendation_service().recommend(top_n=top_n)
        data = self._recommendation_data(recommendations)
        reasoning = (
            "Loaded your career profile.",
            "Scored every qualified job against your profile and ranked them by match.",
        )
        message_text = self._format_recommendations(recommendations)
        return self._ok(AgentIntent.RECOMMEND, message_text, data, reasoning)

    def _list_recommendations(self, message: str) -> AgentResponse:
        top_n = self._extract_top_n(message)
        recommendations = self._recommendation_service().list_recommendations(top_n=top_n)
        data = self._recommendation_data(recommendations)
        reasoning = (
            "Loaded the persisted recommendations from the previous run.",
        )
        message_text = self._format_recommendations(recommendations, listing=True)
        return self._ok(AgentIntent.LIST_RECOMMENDATIONS, message_text, data, reasoning)

    def _ai_explain(self, message: str) -> AgentResponse:
        job_id = self._extract_recommendation_id(message)
        if job_id is None:
            return self._error(
                AgentIntent.AI_EXPLAIN,
                "Which recommendation should I explain? Provide a job ID, for example "
                "`explain job 42`.",
                reasoning=("No job ID was found in the message.",),
            )

        recommendations = self._recommendation_service().list_recommendations(top_n=500)
        target = next((r for r in recommendations if r.job_id == job_id), None)
        if target is None:
            return self._error(
                AgentIntent.AI_EXPLAIN,
                f"There is no recommendation for job #{job_id} yet. Run `recommend` first.",
                reasoning=(f"Looked for a persisted recommendation for job #{job_id}.",),
            )

        job_title, company = self._job_meta(job_id)
        service = self._get_service("explanation", self._build_explanation_service)
        result = service.explain(target, job_title=job_title, company=company)

        data: dict[str, Any] = {"job_id": job_id, **result.to_dict()}
        reasoning = (
            f"Selected the recommendation for job #{job_id}.",
            "Passed its deterministic match data to the explanation model.",
            "Returned the generated explanation.",
        )
        return self._ok(AgentIntent.AI_EXPLAIN, result.explanation, data, reasoning)

    def _pipeline(self, _message: str) -> AgentResponse:
        service = self._get_service("pipeline", self._build_pipeline_service)
        result = service.run()
        data: dict[str, Any] = {
            "run_id": result.run_id,
            "jobs_found": result.jobs_found,
            "duplicates_removed": result.duplicates_removed,
            "matched": result.matched,
            "ai_completed": result.ai_completed,
            "ai_failed": result.ai_failed,
            "packages_created": result.packages_created,
            "queued": result.queued,
            "errors": result.errors[:10] if result.errors else [],
            "duration_seconds": round(result.duration_seconds, 2),
        }
        reasoning = (
            "Ran the full pipeline: discovery, matching, AI tailoring, rendering and approval "
            "queueing.",
        )
        message_text = (
            f"Pipeline run #{result.run_id} finished in {result.duration_seconds:.1f}s: "
            f"{result.jobs_found} jobs found, {result.matched} matched, "
            f"{result.packages_created} packages created and {result.queued} queued for approval."
        )
        return self._ok(AgentIntent.PIPELINE, message_text, data, reasoning)

    def _application_analytics(self, _message: str) -> AgentResponse:
        service = self._get_service("application", self._build_application_service)
        analytics = service.analytics()
        summary = service.summarize()
        data: dict[str, Any] = {"summary": summary, "analytics": analytics}

        counts = analytics.get("counts", {})
        rates = analytics.get("rates", {})
        message_text = (
            f"You have {counts.get('submitted', 0)} submitted applications; "
            f"{counts.get('interview', 0)} reached an interview and {counts.get('offer', 0)} "
            f"received an offer. Interview rate is {rates.get('interview_rate', 0.0)}% and offer "
            f"rate is {rates.get('offer_rate', 0.0)}%."
        )
        reasoning = (
            "Queried your tracked applications.",
            "Aggregated funnel counts, rates and average response time.",
        )
        return self._ok(AgentIntent.APPLICATION_ANALYTICS, message_text, data, reasoning)

    def _approval_queue(self, _message: str) -> AgentResponse:
        service = self._get_service("approval", self._build_approval_service)
        queue_size = service.queue_count()
        packages = service.peek_queue(limit=10)
        data: dict[str, Any] = {
            "queue_size": queue_size,
            "packages": [p.to_dict() for p in packages],
        }
        reasoning = ("Read the current approval queue.",)
        if queue_size == 0:
            message_text = "Your approval queue is empty. Nothing is waiting on you."
        else:
            message_text = (
                f"There are {queue_size} applications waiting for your approval. "
                "Run `approval queue` in the CLI or use Telegram to review them."
            )
        return self._ok(AgentIntent.APPROVAL_QUEUE, message_text, data, reasoning)

    #  Service wiring

    def _get_service(self, key: str, factory: Callable[[], Any]) -> Any:  # noqa: ANN401
        if key not in self._services:
            self._services[key] = factory()
        return self._services[key]

    def _build_profile_service(self) -> ProfileService:
        return ProfileService(
            session=self._session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )

    def _build_discovery_service(self) -> DiscoveryService:
        registry = build_connector_registry(self._settings)
        filter_service = HardFilterService(self._settings.filter_rules)
        duplicate_service = DuplicateDetectionService(
            self._session,
            fuzzy_threshold=self._settings.filter_rules.fuzzy_title_threshold,
        )
        matching_service = JobMatchingService(self._session, filter_service, duplicate_service)
        return DiscoveryService(
            session=self._session,
            connector_registry=registry,
            normalizer=JobNormalizationService(),
            matching_service=matching_service,
        )

    def _recommendation_service(self) -> RecommendationService:
        return self._get_service("recommendation", self._build_recommendation_service)

    def _build_recommendation_service(self) -> RecommendationService:
        return RecommendationService(session=self._session)

    def _build_explanation_service(self) -> ExplanationService:
        orchestrator = AIOrchestrator(
            ai_config=get_ai_config(),
            settings=self._settings,
            session=self._session,
        )
        return ExplanationService(orchestrator=orchestrator)

    def _build_pipeline_service(self) -> PipelineOrchestrator:
        return PipelineOrchestrator(session=self._session, settings=self._settings)

    def _build_application_service(self) -> ApplicationService:
        return ApplicationService(session=self._session)

    def _build_approval_service(self) -> ApprovalService:
        return ApprovalService(session=self._session)

    #  Helpers

    def _ok(
        self,
        intent: AgentIntent,
        message: str,
        data: dict[str, Any],
        reasoning: tuple[str, ...],
    ) -> AgentResponse:
        return AgentResponse(
            intent=intent,
            message=message,
            data=data,
            reasoning=reasoning,
            success=True,
        )

    def _error(
        self,
        intent: AgentIntent,
        message: str,
        reasoning: tuple[str, ...],
    ) -> AgentResponse:
        return AgentResponse(
            intent=intent,
            message=message,
            data={},
            reasoning=reasoning,
            success=False,
            error=message,
        )

    def _error_response(
        self,
        intent: AgentIntent,
        _message: str,
        exc: Exception,
        hint: str | None = None,
    ) -> AgentResponse:
        detail = f"{exc}"
        text = f"I could not complete that request. {detail}"
        if hint:
            text = f"{text} {hint}"
        return AgentResponse(
            intent=intent,
            message=text,
            data={"error": detail},
            reasoning=("An error occurred while orchestrating the requested capability.",),
            success=False,
            error=detail,
        )

    def _job_meta(self, job_id: int) -> tuple[str, str]:
        row = self._session.get(JobRecord, job_id)
        if row is None:
            return ("", "")
        return (row.title or "", row.company or "")

    def _recommendation_data(self, recommendations: list[Any]) -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = []
        for rec in recommendations:
            entry = rec.to_dict()
            job_title, company = self._job_meta(rec.job_id)
            entry["job_title"] = job_title
            entry["company"] = company
            data.append(entry)
        return data

    def _format_recommendations(
        self, recommendations: list[Any], listing: bool = False
    ) -> str:
        if not recommendations:
            return (
                "There are no recommendations right now. Run `discover jobs` to fetch postings "
                "and make sure a career profile has been imported."
            )
        lines = []
        for rec in recommendations[:3]:
            job_title, company = self._job_meta(rec.job_id)
            heading = job_title or f"Job #{rec.job_id}"
            if company:
                heading = f"{heading} at {company}"
            summary = ""
            if rec.insights is not None and rec.insights.summary:
                summary = f"  {rec.insights.summary}"
            lines.append(
                f"{rec.ranking_position}. {heading} (score {rec.final_score:.0f}){summary}"
            )
        prefix = "Here are your top matches:" if not listing else "Persisted recommendations:"
        return "\n".join([prefix, *lines])

    @staticmethod
    def _display_name(full_name: str) -> str:
        return f" for {full_name}" if full_name else ""

    @staticmethod
    def _list_updates(updated: dict[str, str]) -> str:
        if not updated:
            return ""
        labels = {"name": "name", "summary": "summary"}
        return " " + ", ".join(labels[key] for key in updated)

    @staticmethod
    def _extract_path(message: str) -> str | None:
        candidates: list[str] = []
        for pattern in (_ABS_PATH_RE, _REL_PATH_RE, _EXT_PATH_RE):
            candidates.extend(m.group(0).strip("\"' ") for m in pattern.finditer(message))
        if not candidates:
            return None
        return max(candidates, key=len)

    @staticmethod
    def _extract_top_n(message: str) -> int | None:
        for pattern in (_TOP_FLAG_RE, _TOP_PHRASE_RE, _TRAILING_N_RE):
            match = pattern.search(message)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _extract_recommendation_id(message: str) -> int | None:
        match = _LABELED_ID_RE.search(message)
        if match:
            return int(match.group(1))
        match = _FIRST_INT_RE.search(message)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_flag(message: str, pattern: re.Pattern[str]) -> str | None:
        match = pattern.search(message)
        if match:
            value = match.group(1).strip()
            return value or None
        return None

    @staticmethod
    def _extract_summary_to(message: str) -> str | None:
        match = _SUMMARY_TO_RE.search(message)
        if match:
            value = match.group(1).strip()
            return value or None
        return None

