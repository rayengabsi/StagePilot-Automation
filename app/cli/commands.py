from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.config.ai_config import get_ai_config
from app.config.logging import configure_logging
from app.config.settings import Settings, get_settings
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector
from app.infrastructure.parsers.pdf_parser import PDFParser
from app.services.ai_orchestrator import AIOrchestrator
from app.services.approval_service import ApprovalService
from app.services.cover_letter_service import CoverLetterService
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.email_draft_service import EmailDraftService
from app.services.explanation_service import ExplanationService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.job_source_repository import JobSourceRepository
from app.services.profile_normalizer import ProfileNormalizer
from app.services.profile_service import ProfileService
from app.services.profile_validator import ProfileValidator
from app.services.prompt_service import PromptService
from app.services.recommendation_service import RecommendationService
from app.services.resume_tailor_service import ResumeTailorService


def run_cli(argv: list[str] | None = None) -> int:
    """Run the StagePilot command-line interface."""
    settings = get_settings()
    configure_logging(settings)
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    return args.handler(args, settings)


def _build_parser() -> argparse.ArgumentParser:
    """Build the root CLI parser."""
    parser = argparse.ArgumentParser(prog="stagepilot")
    subparsers = parser.add_subparsers(dest="command")

    discover_parser = subparsers.add_parser("discover", help="Run job discovery once.")
    discover_parser.add_argument(
        "--backfill",
        action="store_true",
        help="Also process existing jobs that lack match records.",
    )
    discover_parser.set_defaults(handler=_handle_discover)

    sources_parser = subparsers.add_parser("sources", help="Manage job sources.")
    sources_subparsers = sources_parser.add_subparsers(dest="sources_command")

    add_rss_parser = sources_subparsers.add_parser("add-rss", help="Add an RSS/Atom job source.")
    add_rss_parser.add_argument("--name", required=True, help="Unique source name.")
    add_rss_parser.add_argument("--url", required=True, help="RSS or Atom feed URL.")
    add_rss_parser.set_defaults(handler=_handle_add_rss_source)

    list_parser = sources_subparsers.add_parser("list", help="List configured job sources.")
    list_parser.set_defaults(handler=_handle_list_sources)

    profile_parser = subparsers.add_parser("profile", help="Manage the master profile.")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")

    import_parser = profile_subparsers.add_parser("import", help="Import a resume PDF.")
    import_parser.add_argument("file", type=str, help="Path to the resume PDF file.")
    import_parser.add_argument(
        "--description", type=str, default=None, help="Change description for versioning."
    )
    import_parser.set_defaults(handler=_handle_profile_import)

    show_parser = profile_subparsers.add_parser("show", help="Show the current profile.")
    show_parser.set_defaults(handler=_handle_profile_show)

    export_parser = profile_subparsers.add_parser(
        "export", help="Export the current profile as JSON."
    )
    export_parser.add_argument(
        "--output", type=str, default="profile_export.json", help="Output file path."
    )
    export_parser.set_defaults(handler=_handle_profile_export)

    versions_parser = profile_subparsers.add_parser("versions", help="List profile versions.")
    versions_parser.set_defaults(handler=_handle_profile_versions)

    recommend_parser = subparsers.add_parser(
        "recommend", help="Run the recommendation engine against qualified jobs."
    )
    recommend_parser.add_argument(
        "--top", type=int, default=None, help="Limit to top N recommendations."
    )
    recommend_parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    recommend_parser.add_argument(
        "--list", action="store_true", help="List persisted recommendations instead of running."
    )
    recommend_parser.set_defaults(handler=_handle_recommend)

    feedback_parser = subparsers.add_parser(
        "feedback", help="Submit feedback for a recommendation."
    )
    feedback_parser.add_argument("recommendation_id", type=int, help="Recommendation record ID.")
    feedback_parser.add_argument(
        "--reason",
        required=True,
        choices=[
            "wrong_country",
            "wrong_field",
            "wrong_technologies",
            "too_senior",
            "salary",
            "not_remote",
            "other",
        ],
        help="Feedback reason.",
    )
    feedback_parser.add_argument(
        "--comment", type=str, default=None, help="Optional free text comment."
    )
    feedback_parser.set_defaults(handler=_handle_feedback)

    ai_parser = subparsers.add_parser("ai", help="AI-powered features.")
    ai_subparsers = ai_parser.add_subparsers(dest="ai_command")

    ai_explain = ai_subparsers.add_parser(
        "explain", help="Generate explanation for a recommendation."
    )
    ai_explain.add_argument("recommendation_id", type=int, help="Recommendation ID.")
    ai_explain.add_argument("--job-title", type=str, default="", help="Job title for context.")
    ai_explain.add_argument("--company", type=str, default="", help="Company name for context.")
    ai_explain.set_defaults(handler=_handle_ai_explain)

    ai_tailor = ai_subparsers.add_parser("tailor-resume", help="Tailor resume for a specific job.")
    ai_tailor.add_argument("recommendation_id", type=int, help="Recommendation ID.")
    ai_tailor.add_argument("--job-description", type=str, default="", help="Job description text.")
    ai_tailor.set_defaults(handler=_handle_ai_tailor)

    ai_cover = ai_subparsers.add_parser("cover-letter", help="Generate a cover letter.")
    ai_cover.add_argument("recommendation_id", type=int, help="Recommendation ID.")
    ai_cover.add_argument("--company", type=str, default="", help="Company name.")
    ai_cover.add_argument("--recipient", type=str, default="", help="Recipient name.")
    ai_cover.set_defaults(handler=_handle_ai_cover_letter)

    ai_email = ai_subparsers.add_parser("email", help="Draft an application email.")
    ai_email.add_argument("recommendation_id", type=int, help="Recommendation ID.")
    ai_email.add_argument("--company", type=str, default="", help="Company name.")
    ai_email.add_argument("--recipient", type=str, default="", help="Recipient name.")
    ai_email.add_argument("--job-title", type=str, default="", help="Job title.")
    ai_email.set_defaults(handler=_handle_ai_email)

    ai_usage_parser = ai_subparsers.add_parser("usage", help="Show AI token usage.")
    ai_usage_parser.add_argument("--limit", type=int, default=20, help="Number of records to show.")
    ai_usage_parser.add_argument("--feature", type=str, default=None, help="Filter by feature.")
    ai_usage_parser.set_defaults(handler=_handle_ai_usage)

    ai_prompts_parser = ai_subparsers.add_parser("prompts", help="List available AI prompts.")
    ai_prompts_parser.set_defaults(handler=_handle_ai_prompts)

    render_parser = subparsers.add_parser("render", help="Render documents (resume, cover letter).")
    render_subparsers = render_parser.add_subparsers(dest="render_command")

    r_resume = render_subparsers.add_parser("resume", help="Render a resume.")
    r_resume.add_argument(
        "--template",
        type=str,
        default=None,
        help="Template name (modern, executive, minimal, classic, professional).",
    )
    r_resume.add_argument(
        "--theme",
        type=str,
        default=None,
        help="Theme name from config/theme.toml.",
    )
    r_resume.add_argument(
        "--format",
        type=str,
        default="pdf",
        choices=["pdf", "docx", "all"],
        help="Output format.",
    )
    r_resume.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: output/resume.pdf).",
    )
    r_resume.set_defaults(handler=_handle_render_resume)

    r_cover = render_subparsers.add_parser(
        "cover-letter",
        help="Render a cover letter.",
    )
    r_cover.add_argument(
        "--template",
        type=str,
        default=None,
        help="Template name.",
    )
    r_cover.add_argument("--theme", type=str, default=None, help="Theme name.")
    r_cover.add_argument(
        "--format",
        type=str,
        default="pdf",
        choices=["pdf", "docx", "all"],
        help="Output format.",
    )
    r_cover.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: output/cover_letter.pdf).",
    )
    r_cover.set_defaults(handler=_handle_render_cover_letter)

    r_tpl = render_subparsers.add_parser("templates", help="List available templates.")
    r_tpl.set_defaults(handler=_handle_render_templates)

    r_thm = render_subparsers.add_parser("themes", help="List available themes.")
    r_thm.set_defaults(handler=_handle_render_themes)

    r_preview = render_subparsers.add_parser("preview", help="Preview rendering setup (dry run).")
    r_preview.add_argument("--template", type=str, default=None, help="Template name.")
    r_preview.add_argument("--theme", type=str, default=None, help="Theme name.")
    r_preview.set_defaults(handler=_handle_render_preview)

    approval_parser = subparsers.add_parser("approval", help="Manage the approval queue.")
    approval_subparsers = approval_parser.add_subparsers(dest="approval_command")

    a_queue_parser = approval_subparsers.add_parser("queue", help="Show the approval queue.")
    a_queue_parser.add_argument(
        "--limit", type=int, default=10, help="Number of items (default: 10)."
    )
    a_queue_parser.add_argument("--offset", type=int, default=0, help="Offset (default: 0).")
    a_queue_parser.set_defaults(handler=_handle_approval_queue)

    a_list_parser = approval_subparsers.add_parser("list", help="List all packages.")
    a_list_parser.add_argument("--status", type=str, default=None, help="Filter by status.")
    a_list_parser.add_argument("--limit", type=int, default=50, help="Limit (default: 50).")
    a_list_parser.set_defaults(handler=_handle_approval_list)

    a_approve_parser = approval_subparsers.add_parser("approve", help="Approve a package.")
    a_approve_parser.add_argument("package_id", type=int, help="Package ID.")
    a_approve_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    a_approve_parser.add_argument("--comment", type=str, default="", help="Approval comment.")
    a_approve_parser.set_defaults(handler=_handle_approval_approve)

    a_reject_parser = approval_subparsers.add_parser("reject", help="Reject a package.")
    a_reject_parser.add_argument("package_id", type=int, help="Package ID.")
    a_reject_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    a_reject_parser.add_argument("--comment", type=str, default="", help="Rejection comment.")
    a_reject_parser.set_defaults(handler=_handle_approval_reject)

    a_revise_parser = approval_subparsers.add_parser(
        "revise", help="Request revision for a package."
    )
    a_revise_parser.add_argument("package_id", type=int, help="Package ID.")
    a_revise_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    a_revise_parser.add_argument("--comment", type=str, default="", help="Revision comment.")
    a_revise_parser.set_defaults(handler=_handle_approval_revise)

    a_skip_parser = approval_subparsers.add_parser("skip", help="Skip a package.")
    a_skip_parser.add_argument("package_id", type=int, help="Package ID.")
    a_skip_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    a_skip_parser.add_argument("--comment", type=str, default="", help="Skip comment.")
    a_skip_parser.set_defaults(handler=_handle_approval_skip)

    a_archive_parser = approval_subparsers.add_parser("archive", help="Archive a package.")
    a_archive_parser.add_argument("package_id", type=int, help="Package ID.")
    a_archive_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    a_archive_parser.add_argument("--comment", type=str, default="", help="Archive comment.")
    a_archive_parser.set_defaults(handler=_handle_approval_archive)

    a_history_parser = approval_subparsers.add_parser("history", help="Show history for a package.")
    a_history_parser.add_argument("package_id", type=int, help="Package ID.")
    a_history_parser.set_defaults(handler=_handle_approval_history)

    telegram_parser = subparsers.add_parser("telegram", help="Telegram integration.")
    telegram_subparsers = telegram_parser.add_subparsers(dest="telegram_command")

    t_run = telegram_subparsers.add_parser("run", help="Run the Telegram bot.")
    t_run.set_defaults(handler=_handle_telegram_run)

    pipeline_parser = subparsers.add_parser("pipeline", help="Run the end-to-end pipeline.")
    pipeline_subparsers = pipeline_parser.add_subparsers(dest="pipeline_command")

    p_run = pipeline_subparsers.add_parser("run", help="Run the full pipeline (discovery → queue).")
    p_run.set_defaults(handler=_handle_pipeline_run)

    p_once = pipeline_subparsers.add_parser("once", help="Run the pipeline once (alias for run).")
    p_once.set_defaults(handler=_handle_pipeline_once)

    scheduler_parser = subparsers.add_parser("scheduler", help="Manage the pipeline scheduler.")
    scheduler_subparsers = scheduler_parser.add_subparsers(dest="scheduler_command")

    s_run = scheduler_subparsers.add_parser("run", help="Run the pipeline once via scheduler.")
    s_run.set_defaults(handler=_handle_scheduler_run)

    s_start = scheduler_subparsers.add_parser("start", help="Start the scheduler loop (blocking).")
    s_start.add_argument(
        "--interval",
        type=str,
        default="daily",
        choices=["hourly", "every_6_hours", "daily"],
        help="Run interval (default: daily).",
    )
    s_start.set_defaults(handler=_handle_scheduler_start)

    return parser


def _handle_approval_queue(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        packages = svc.peek_queue(limit=args.limit, offset=args.offset)
        count = svc.queue_count()
        data = {
            "queue_size": count,
            "packages": [p.to_dict() for p in packages],
        }
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_approval_list(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        packages = svc.list_packages(status=args.status, limit=args.limit)
        data = [p.to_dict() for p in packages]
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_approval_approve(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        updated = svc.approve(package_id=args.package_id, actor=args.actor, comment=args.comment)
    print(json.dumps(updated.to_dict(), indent=2, default=str))
    return 0


def _handle_approval_reject(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        updated = svc.reject(package_id=args.package_id, actor=args.actor, comment=args.comment)
    print(json.dumps(updated.to_dict(), indent=2, default=str))
    return 0


def _handle_approval_revise(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        updated = svc.request_revision(
            package_id=args.package_id, actor=args.actor, comment=args.comment
        )
    print(json.dumps(updated.to_dict(), indent=2, default=str))
    return 0


def _handle_approval_skip(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        updated = svc.skip(package_id=args.package_id, actor=args.actor, comment=args.comment)
    print(json.dumps(updated.to_dict(), indent=2, default=str))
    return 0


def _handle_approval_archive(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        updated = svc.archive(package_id=args.package_id, actor=args.actor, comment=args.comment)
    print(json.dumps(updated.to_dict(), indent=2, default=str))
    return 0


def _handle_approval_history(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApprovalService(session=session)
        events = svc.get_history(args.package_id)
        data = [e.to_dict() for e in events]
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_telegram_run(_args: argparse.Namespace, settings: Settings) -> int:
    from app.infrastructure.telegram.bot import run_telegram_bot

    run_telegram_bot(settings)
    return 0


def _handle_pipeline_run(args: argparse.Namespace, settings: Settings) -> int:
    return _execute_pipeline(args, settings)


def _handle_pipeline_once(args: argparse.Namespace, settings: Settings) -> int:
    return _execute_pipeline(args, settings)


def _execute_pipeline(_args: argparse.Namespace, settings: Settings) -> int:
    from app.services.pipeline_orchestrator import PipelineOrchestrator

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        orchestrator = PipelineOrchestrator(session=session, settings=settings)
        result = orchestrator.run()
        summary = {
            "run_id": result.run_id,
            "jobs_found": result.jobs_found,
            "duplicates_removed": result.duplicates_removed,
            "matched": result.matched,
            "below_threshold": result.below_threshold,
            "ai_completed": result.ai_completed,
            "ai_failed": result.ai_failed,
            "rendering_completed": result.rendering_completed,
            "rendering_failed": result.rendering_failed,
            "packages_created": result.packages_created,
            "queued": result.queued,
            "telegram_sent": result.telegram_sent,
            "duration_seconds": round(result.duration_seconds, 2),
            "errors": result.errors[:10] if result.errors else [],
        }
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _handle_scheduler_run(_args: argparse.Namespace, settings: Settings) -> int:
    from app.services.scheduler_service import SchedulerService

    svc = SchedulerService(settings=settings)
    result = svc.run_once()
    print(json.dumps(result, indent=2))
    return 0


def _handle_scheduler_start(args: argparse.Namespace, settings: Settings) -> int:
    from app.services.scheduler_service import ScheduleInterval, SchedulerService

    interval_str = getattr(args, "interval", "daily")
    interval = ScheduleInterval(interval_str)
    svc = SchedulerService(settings=settings)
    svc.start(interval)
    return 0


def _handle_discover(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the discovery command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        registry = ConnectorRegistry([RssFeedConnector(settings)])
        filter_service = HardFilterService(settings.filter_rules)
        duplicate_service = DuplicateDetectionService(
            session, fuzzy_threshold=settings.filter_rules.fuzzy_title_threshold
        )
        matching_service = JobMatchingService(session, filter_service, duplicate_service)
        service = DiscoveryService(
            session=session,
            connector_registry=registry,
            normalizer=JobNormalizationService(),
            matching_service=matching_service,
        )
        backfill = getattr(args, "backfill", False) or False
        summary = service.run_once(backfill_existing=backfill)

    print(json.dumps(asdict(summary), sort_keys=True))
    return 0


def _handle_add_rss_source(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the command that adds an RSS source."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        source = JobSourceRepository(session).add_rss_source(name=args.name, url=args.url)
        payload = {
            "id": source.id,
            "name": source.name,
            "type": source.type,
            "base_url": source.base_url,
        }

    print(json.dumps(payload, sort_keys=True))
    return 0


def _build_profile_service(settings: Settings) -> ProfileService:
    """Build a ProfileService with its dependencies."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    session = session_factory()
    return ProfileService(
        session=session,
        parser=PDFParser(),
        normalizer=ProfileNormalizer(),
        validator=ProfileValidator(),
    )


def _handle_profile_import(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile import command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        file_path = Path(args.file)
        if not file_path.exists():
            print(json.dumps({"error": f"File not found: {file_path}"}))
            return 1
        profile = service.import_resume(file_path, description=args.description)
        completeness = service.get_completeness()
        result = {
            "status": "imported",
            "full_name": profile.personal_info.full_name,
            "education_count": len(profile.education),
            "experience_count": len(profile.experience),
            "skills_count": len(profile.skills),
            "projects_count": len(profile.projects),
            "languages_count": len(profile.languages),
            "certifications_count": len(profile.certifications),
            "completeness_score": completeness.score,
            "completeness_breakdown": completeness.breakdown,
            "missing_fields": list(completeness.missing_fields),
        }
    print(json.dumps(result, sort_keys=True))
    return 0


def _handle_profile_show(_args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile show command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        try:
            profile = service.get_current_profile()
            completeness = service.get_completeness()
            data = profile.to_dict()
            data["completeness_score"] = completeness.score
            data["completeness_breakdown"] = completeness.breakdown
            data["missing_fields"] = list(completeness.missing_fields)
        except Exception as exc:
            data = {"error": str(exc)}
    print(json.dumps(data, sort_keys=True, indent=2, default=str))
    return 0


def _handle_profile_export(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile export command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        try:
            output_path = Path(args.output)
            service.export_profile(output_path)
            result = {"status": "exported", "path": str(output_path.resolve())}
        except Exception as exc:
            result = {"error": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return 0


def _handle_profile_versions(_args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile versions command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        try:
            versions = service.list_versions()
            data = [
                {
                    "version": v.version_number,
                    "completeness_score": v.completeness_score,
                    "change_description": v.change_description,
                    "created_at": v.created_at,
                    "full_name": v.profile.personal_info.full_name,
                }
                for v in versions
            ]
        except Exception as exc:
            data = {"error": str(exc)}
    print(json.dumps(data, sort_keys=True, indent=2, default=str))
    return 0


def _handle_list_sources(_args: argparse.Namespace, settings: Settings) -> int:
    """Handle the command that lists configured sources."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        sources = [
            {
                "id": source.id,
                "name": source.name,
                "type": source.type,
                "base_url": source.base_url,
                "is_active": source.is_active,
            }
            for source in JobSourceRepository(session).list_sources()
        ]

    print(json.dumps(sources, sort_keys=True))
    return 0


def _handle_recommend(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the recommend command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = RecommendationService(session=session)

        if getattr(args, "list", False):
            recommendations = service.list_recommendations(top_n=args.top)
        else:
            recommendations = service.recommend(top_n=args.top)

        output = []
        for rec in recommendations:
            entry = rec.to_dict()
            output.append(entry)

    if getattr(args, "json", False):
        print(json.dumps(output, sort_keys=True, indent=2, default=str))
    else:
        if not output:
            print("No recommendations found.")
            return 0
        print(f"{'Rank':<6}{'Score':<8}{'Job ID':<8}{'Status':<12}{'Matched Skills'}")
        print("-" * 80)
        for rec in output:
            matched = ", ".join(rec["matched_detail"]["matched_skills"][:5])
            if len(rec["matched_detail"]["matched_skills"]) > 5:
                matched += "..."
            print(
                f"{rec['ranking_position']:<6}"
                f"{rec['final_score']:<8.1f}"
                f"{rec['job_id']:<8}"
                f"{rec['status']:<12}"
                f"{matched}"
            )
    return 0


def _handle_feedback(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the feedback command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = RecommendationService(session=session)
        fb = service.feedback(
            recommendation_id=args.recommendation_id,
            reason=args.reason,
            comment=args.comment,
        )
        result = {
            "recommendation_id": fb.recommendation_id,
            "reason": fb.reason,
            "comment": fb.comment,
            "created_at": fb.created_at,
        }
    print(json.dumps(result, sort_keys=True))
    return 0


def _build_orchestrator(settings: Settings) -> AIOrchestrator:
    """Build an AIOrchestrator with injected dependencies."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    session = session_factory()
    ai_config = get_ai_config()
    return AIOrchestrator(ai_config=ai_config, settings=settings, session=session)


def _handle_ai_explain(args: argparse.Namespace, settings: Settings) -> int:
    """Handle ai explain command."""
    from app.services.recommendation_service import RecommendationService

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        rec_service = RecommendationService(session=session)
        recs = rec_service.list_recommendations(top_n=100)
        target = next((r for r in recs if r.job_id == args.recommendation_id), None)
        if not target:
            msg = f"Recommendation for job {args.recommendation_id} not found"
            print(json.dumps({"error": msg}))
            return 1
        orchestrator = AIOrchestrator(ai_config=get_ai_config(), settings=settings, session=session)
        svc = ExplanationService(orchestrator=orchestrator)
        result = svc.explain(target, job_title=args.job_title, company=args.company)
    print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
    return 0


def _handle_ai_tailor(args: argparse.Namespace, settings: Settings) -> int:
    """Handle ai tailor-resume command."""
    from app.infrastructure.parsers.pdf_parser import PDFParser
    from app.services.profile_normalizer import ProfileNormalizer
    from app.services.profile_service import ProfileService
    from app.services.profile_validator import ProfileValidator
    from app.services.recommendation_service import RecommendationService

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        rec_service = RecommendationService(session=session)
        recs = rec_service.list_recommendations(top_n=100)
        target = next((r for r in recs if r.job_id == args.recommendation_id), None)
        if not target:
            msg = f"Recommendation for job {args.recommendation_id} not found"
            print(json.dumps({"error": msg}))
            return 1
        profile_service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        profile = profile_service.get_current_profile()
        orchestrator = AIOrchestrator(ai_config=get_ai_config(), settings=settings, session=session)
        svc = ResumeTailorService(orchestrator=orchestrator)
        result = svc.tailor(profile, target, job_description=args.job_description)
    print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
    return 0


def _handle_ai_cover_letter(args: argparse.Namespace, settings: Settings) -> int:
    """Handle ai cover-letter command."""
    from app.infrastructure.parsers.pdf_parser import PDFParser
    from app.services.profile_normalizer import ProfileNormalizer
    from app.services.profile_service import ProfileService
    from app.services.profile_validator import ProfileValidator
    from app.services.recommendation_service import RecommendationService

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        rec_service = RecommendationService(session=session)
        recs = rec_service.list_recommendations(top_n=100)
        target = next((r for r in recs if r.job_id == args.recommendation_id), None)
        if not target:
            msg = f"Recommendation for job {args.recommendation_id} not found"
            print(json.dumps({"error": msg}))
            return 1
        profile_service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        profile = profile_service.get_current_profile()
        orchestrator = AIOrchestrator(ai_config=get_ai_config(), settings=settings, session=session)
        svc = CoverLetterService(orchestrator=orchestrator)
        result = svc.generate(
            profile,
            target,
            company=args.company,
            recipient=args.recipient,
        )
    print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
    return 0


def _handle_ai_email(args: argparse.Namespace, settings: Settings) -> int:
    """Handle ai email command."""
    from app.infrastructure.parsers.pdf_parser import PDFParser
    from app.services.cover_letter_service import CoverLetterService
    from app.services.profile_normalizer import ProfileNormalizer
    from app.services.profile_service import ProfileService
    from app.services.profile_validator import ProfileValidator

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        profile_service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        profile = profile_service.get_current_profile()
        orchestrator = AIOrchestrator(ai_config=get_ai_config(), settings=settings, session=session)
        cover_svc = CoverLetterService(orchestrator=orchestrator)
        cover_letter = cover_svc.generate(
            profile,
            None,  # type: ignore[arg-type]
            company=args.company,
            recipient=args.recipient,
        )
        email_svc = EmailDraftService(orchestrator=orchestrator)
        result = email_svc.draft(
            cover_letter=cover_letter,
            company=args.company,
            job_title=args.job_title,
            recipient=args.recipient,
            candidate_name=profile.personal_info.full_name,
        )
    print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
    return 0


def _handle_ai_usage(args: argparse.Namespace, settings: Settings) -> int:
    """Handle ai usage command."""
    from app.services.token_tracker import TokenTracker

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        tracker = TokenTracker(session=session)
        records = tracker.get_usage(limit=args.limit, feature=args.feature)
        data = [r.to_dict() for r in records]
    if data:
        print(json.dumps(data, sort_keys=True, indent=2))
    else:
        print("No AI usage records found.")
    return 0


def _handle_ai_prompts(_args: argparse.Namespace, _settings: Settings) -> int:
    """Handle ai prompts command."""
    svc = PromptService()
    prompts = svc.list_prompts()
    print(json.dumps(prompts, sort_keys=True, indent=2))
    return 0


def _handle_render_resume(args: argparse.Namespace, settings: Settings) -> int:
    """Handle render resume command."""
    from app.infrastructure.parsers.pdf_parser import PDFParser
    from app.rendering.renderer_factory import RendererFactory
    from app.services.profile_normalizer import ProfileNormalizer
    from app.services.profile_service import ProfileService
    from app.services.profile_validator import ProfileValidator

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        profile_service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        profile = profile_service.get_current_profile()
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    fmt = args.format
    formats = ["pdf", "docx"] if fmt == "all" else [fmt]
    factory = RendererFactory()
    results = factory.render_resume_all(
        profile,
        output_dir,
        template_name=args.template,
        formats=formats,
    )
    for r in results:
        print(
            json.dumps(
                {
                    "path": str(r.path),
                    "format": r.format,
                    "sections_rendered": r.sections_rendered,
                    "template": r.template_used,
                },
                indent=2,
            )
        )
    return 0


def _handle_render_cover_letter(args: argparse.Namespace, settings: Settings) -> int:
    """Handle render cover-letter command."""
    from app.infrastructure.parsers.pdf_parser import PDFParser
    from app.rendering.models import CoverLetterData
    from app.rendering.renderer_factory import RendererFactory
    from app.services.profile_normalizer import ProfileNormalizer
    from app.services.profile_service import ProfileService
    from app.services.profile_validator import ProfileValidator

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        profile_service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        profile = profile_service.get_current_profile()
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    cover_body = (
        "Dear Hiring Manager,\n\n"
        "I am writing to express my strong interest in this position. "
        "With my background and skills, I am confident I can contribute "
        "effectively to your team.\n\n"
        "Thank you for your consideration.\n\nSincerely,\n"
        f"{profile.personal_info.full_name}"
    )
    cover_data = CoverLetterData(
        body=cover_body,
        candidate_name=profile.personal_info.full_name,
    )

    fmt = args.format
    formats = ["pdf", "docx"] if fmt == "all" else [fmt]
    factory = RendererFactory()
    results = factory.render_cover_letter_all(
        profile,
        cover_data,
        output_dir,
        template_name=args.template,
        formats=formats,
    )
    for r in results:
        print(
            json.dumps(
                {
                    "path": str(r.path),
                    "format": r.format,
                    "template": r.template_used,
                },
                indent=2,
            )
        )
    return 0


def _handle_render_templates(_args: argparse.Namespace, _settings: Settings) -> int:
    """Handle render templates command."""
    from app.rendering.template_loader import load_all_templates

    templates = load_all_templates()
    print(json.dumps(templates, indent=2))
    return 0


def _handle_render_themes(_args: argparse.Namespace, _settings: Settings) -> int:
    """Handle render themes command."""
    from app.rendering.theme_loader import load_default_theme

    theme = load_default_theme()
    print(json.dumps({"name": theme.name, "configured": True}, indent=2))
    return 0


def _handle_render_preview(args: argparse.Namespace, _settings: Settings) -> int:
    """Handle render preview command (dry run)."""
    from app.rendering.template_loader import TemplateLoader
    from app.rendering.theme_loader import ThemeLoader

    tpl_loader = TemplateLoader()
    tpl_name = args.template or "modern"
    try:
        template = tpl_loader.load(tpl_name)
    except FileNotFoundError:
        print(json.dumps({"error": f"Template '{tpl_name}' not found"}))
        return 1
    theme_loader = ThemeLoader()
    theme = theme_loader.load()
    effective = theme.apply_to(template)
    print(
        json.dumps(
            {
                "template": effective.name,
                "theme": theme.name,
                "page_size": effective.page_size,
                "columns": effective.columns,
                "font_family": effective.fonts.family,
                "section_order": list(effective.section_order),
                "colors": {
                    "primary": effective.colors.primary,
                    "secondary": effective.colors.secondary,
                    "accent": effective.colors.accent,
                },
                "margins": {
                    "top": effective.spacing.page_margin_top,
                    "left": effective.spacing.page_margin_left,
                },
            },
            indent=2,
        )
    )
    return 0
