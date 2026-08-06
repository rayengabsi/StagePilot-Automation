from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select

from app.config.ai_config import get_ai_config
from app.config.logging import configure_logging
from app.config.settings import Settings, get_settings
from app.db.models.profile import Profile
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.domain.master_profile.errors import ProfileValidationError
from app.domain.master_profile.errors import ValidationError as ProfileValidationIssue
from app.infrastructure.job_sources.registry import build_connector_registry
from app.infrastructure.parsers.parser_factory import detect_parser
from app.infrastructure.parsers.pdf_parser import PDFParser
from app.services.ai_orchestrator import AIOrchestrator
from app.services.application_service import ApplicationService
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
from app.services.source_validation_service import SourceValidationService
from app.utils import pii as pii_utils


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

    def _provider_parser(name: str, help_text: str) -> argparse.ArgumentParser:
        parser = sources_subparsers.add_parser(name, help=help_text)
        parser.add_argument("--name", required=True, help="Unique source name.")
        parser.add_argument("--url", required=True, help="Base URL for the provider.")
        parser.add_argument("--company", type=str, default=None, help="Company display name.")
        parser.add_argument("--config", type=str, default=None, help="Extra JSON config.")
        return parser

    add_greenhouse = _provider_parser("add-greenhouse", "Add a Greenhouse job board source.")
    add_greenhouse.add_argument("--token", type=str, default=None, help="Greenhouse board token.")
    add_greenhouse.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "greenhouse", _build_config(a, "token")
        )
    )

    add_lever = _provider_parser("add-lever", "Add a Lever postings source.")
    add_lever.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(a, s, "lever", _build_config(a, "company"))
    )

    add_ashby = _provider_parser("add-ashby", "Add an Ashby job board source.")
    add_ashby.add_argument("--board", type=str, default=None, help="Ashby board identifier.")
    add_ashby.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "ashby", _build_config(a, "board", "company")
        )
    )

    add_smart = _provider_parser("add-smartrecruiters", "Add a SmartRecruiters source.")
    add_smart.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "smart_recruiters", _build_config(a, "company")
        )
    )

    add_teamtailor = _provider_parser("add-teamtailor", "Add a Teamtailor source.")
    add_teamtailor.add_argument("--api-key", type=str, default=None, help="Teamtailor API key.")
    add_teamtailor.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "teamtailor", _build_config(a, "api_key", "company")
        )
    )

    add_wttj = _provider_parser("add-wttj", "Add a Welcome to the Jungle (WelcomeKit) source.")
    add_wttj.add_argument("--slug", type=str, default=None, help="Organization slug.")
    add_wttj.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "welcome_to_the_jungle", _build_config(a, "slug", "company")
        )
    )

    add_remoteok = _provider_parser("add-remoteok", "Add the RemoteOK remote jobs feed.")
    add_remoteok.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "remote_ok", _build_config(a, "company")
        )
    )

    add_wellfound = _provider_parser("add-wellfound", "Add a Wellfound (AngelList) source.")
    add_wellfound.add_argument(
        "--token", type=str, default=None, help="Optional AngelList API token."
    )
    add_wellfound.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "wellfound", _build_config(a, "token", "company")
        )
    )

    add_company = _provider_parser("add-company", "Add a configurable career page source.")
    add_company.add_argument("--selector", required=True, help="CSS selector for job post links.")
    add_company.add_argument("--list-url", type=str, default=None, help="Jobs listing URL.")
    add_company.add_argument("--next-selector", type=str, default=None, help="Next page selector.")
    add_company.add_argument("--title-selector", type=str, default=None, help="Job title selector.")
    add_company.add_argument(
        "--description-selector", type=str, default=None, help="Job description selector."
    )
    add_company.add_argument("--max-pages", type=int, default=1, help="Max listing pages to crawl.")
    add_company.add_argument(
        "--no-scrape-details", action="store_true", help="Do not fetch job detail pages."
    )
    add_company.set_defaults(
        handler=lambda a, s: _handle_add_provider_source(
            a, s, "company_pages", _build_company_config(a)
        )
    )

    add_linkedin_mcp = sources_subparsers.add_parser(
        "add-linkedin-mcp", help="Add a LinkedIn MCP server as the job source."
    )
    add_linkedin_mcp.add_argument("--name", required=True, help="Unique source name.")
    add_linkedin_mcp.add_argument(
        "--command", required=True, help="Executable that starts the MCP server."
    )
    add_linkedin_mcp.add_argument(
        "--args", type=str, default=None, help="Server args (JSON list or shell string)."
    )
    add_linkedin_mcp.add_argument(
        "--env", type=str, default=None, help="Server env overrides as a JSON object."
    )
    add_linkedin_mcp.add_argument("--cwd", type=str, default=None, help="Server working directory.")
    add_linkedin_mcp.add_argument(
        "--tool", type=str, default="search_jobs", help="MCP tool name to call."
    )
    add_linkedin_mcp.add_argument(
        "--keywords", type=str, default=None, help="Search keywords for the LinkedIn query."
    )
    add_linkedin_mcp.add_argument(
        "--location", type=str, default=None, help="Location filter for the search."
    )
    add_linkedin_mcp.add_argument(
        "--job-type", type=str, default=None, help="Employment type filter (e.g. INTERNSHIP)."
    )
    add_linkedin_mcp.add_argument(
        "--limit", type=int, default=None, help="Maximum number of results per search."
    )
    add_linkedin_mcp.add_argument(
        "--timeout", type=int, default=None, help="Per-call timeout in seconds."
    )
    add_linkedin_mcp.set_defaults(handler=_handle_add_linkedin_mcp_source)

    remove_parser = sources_subparsers.add_parser("remove", help="Remove a job source.")
    remove_parser.add_argument("--id", type=int, default=None, help="Source ID to remove.")
    remove_parser.add_argument("--name", type=str, default=None, help="Source name to remove.")
    remove_parser.set_defaults(handler=_handle_remove_source)

    enable_parser = sources_subparsers.add_parser("enable", help="Enable a job source.")
    enable_parser.add_argument("--id", type=int, default=None, help="Source ID.")
    enable_parser.add_argument("--name", type=str, default=None, help="Source name.")
    enable_parser.set_defaults(handler=lambda a, s: _handle_set_source_active(a, s, True))

    disable_parser = sources_subparsers.add_parser("disable", help="Disable a job source.")
    disable_parser.add_argument("--id", type=int, default=None, help="Source ID.")
    disable_parser.add_argument("--name", type=str, default=None, help="Source name.")
    disable_parser.set_defaults(handler=lambda a, s: _handle_set_source_active(a, s, False))

    refresh_parser = sources_subparsers.add_parser("refresh", help="Fetch jobs from one source.")
    refresh_parser.add_argument("--id", type=int, required=True, help="Source ID.")
    refresh_parser.set_defaults(handler=_handle_refresh_source)

    health_parser = sources_subparsers.add_parser("health", help="Check source connectivity.")
    health_parser.add_argument("--id", type=int, required=True, help="Source ID.")
    health_parser.set_defaults(handler=_handle_source_health)

    test_parser = sources_subparsers.add_parser("test", help="Validate a source and dry-run fetch.")
    test_parser.add_argument("--id", type=int, required=True, help="Source ID.")
    test_parser.set_defaults(handler=_handle_test_source)

    list_parser = sources_subparsers.add_parser("list", help="List configured job sources.")
    list_parser.set_defaults(handler=_handle_list_sources)

    benchmark_parser = sources_subparsers.add_parser(
        "benchmark",
        help="Run the connector validation benchmark across configured sources.",
    )
    benchmark_parser.set_defaults(handler=_handle_sources_benchmark)

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

    edit_parser = profile_subparsers.add_parser(
        "edit", help="Edit profile metadata (name, summary)."
    )
    edit_parser.add_argument("--name", type=str, default=None, help="Human-readable profile name.")
    edit_parser.add_argument("--summary", type=str, default=None, help="Professional summary text.")
    edit_parser.add_argument(
        "--profile-id", type=int, default=None, help="Profile ID (default: active)."
    )
    edit_parser.set_defaults(handler=_handle_profile_edit)

    validate_parser = profile_subparsers.add_parser(
        "validate", help="Validate the current profile."
    )
    validate_parser.set_defaults(handler=_handle_profile_validate)

    activate_parser = profile_subparsers.add_parser("activate", help="Activate a profile by ID.")
    activate_parser.add_argument("profile_id", type=int, help="Profile ID to activate.")
    activate_parser.set_defaults(handler=_handle_profile_activate)

    list_parser = profile_subparsers.add_parser("list", help="List all profiles.")
    list_parser.set_defaults(handler=_handle_profile_list)

    delete_parser = profile_subparsers.add_parser("delete", help="Delete a profile by ID.")
    delete_parser.add_argument("profile_id", type=int, help="Profile ID to delete.")
    delete_parser.set_defaults(handler=_handle_profile_delete)

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

    application_parser = subparsers.add_parser(
        "application", help="Manage tracked job applications."
    )
    application_subparsers = application_parser.add_subparsers(dest="application_command")

    app_create_parser = application_subparsers.add_parser(
        "create", help="Create an application from an approved package."
    )
    app_create_parser.add_argument(
        "--package-id", type=int, required=True, help="Approved package ID."
    )
    app_create_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    app_create_parser.set_defaults(handler=_handle_application_create)

    app_list_parser = application_subparsers.add_parser("list", help="List applications.")
    app_list_parser.add_argument("--status", type=str, default=None, help="Filter by status.")
    app_list_parser.add_argument("--company", type=str, default=None, help="Filter by company.")
    app_list_parser.add_argument("--label", type=str, default=None, help="Filter by label.")
    app_list_parser.add_argument(
        "--date-from", type=str, default=None, help="Filter from date (YYYY-MM-DD)."
    )
    app_list_parser.add_argument(
        "--date-to", type=str, default=None, help="Filter to date (YYYY-MM-DD)."
    )
    app_list_parser.add_argument("--limit", type=int, default=50, help="Limit (default: 50).")
    app_list_parser.add_argument("--offset", type=int, default=0, help="Offset (default: 0).")
    app_list_parser.set_defaults(handler=_handle_application_list)

    app_show_parser = application_subparsers.add_parser("show", help="Show an application.")
    app_show_parser.add_argument("application_id", type=int, help="Application ID.")
    app_show_parser.set_defaults(handler=_handle_application_show)

    app_update_parser = application_subparsers.add_parser("update", help="Update an application.")
    app_update_parser.add_argument("application_id", type=int, help="Application ID.")
    app_update_parser.add_argument("--status", type=str, default=None, help="New status.")
    app_update_parser.add_argument("--company", type=str, default=None, help="Company name.")
    app_update_parser.add_argument("--job-title", type=str, default=None, help="Job title.")
    app_update_parser.add_argument("--resume-path", type=str, default=None, help="Resume path.")
    app_update_parser.add_argument(
        "--cover-letter-path", type=str, default=None, help="Cover letter path."
    )
    app_update_parser.add_argument(
        "--labels", type=str, default=None, help="Replace labels (comma-separated)."
    )
    app_update_parser.add_argument("--add-label", type=str, default=None, help="Add a label.")
    app_update_parser.add_argument("--remove-label", type=str, default=None, help="Remove a label.")
    app_update_parser.add_argument("--note", type=str, default=None, help="Add a note.")
    app_update_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    app_update_parser.add_argument("--comment", type=str, default="", help="Transition comment.")
    app_update_parser.set_defaults(handler=_handle_application_update)

    app_archive_parser = application_subparsers.add_parser(
        "archive", help="Archive an application."
    )
    app_archive_parser.add_argument("application_id", type=int, help="Application ID.")
    app_archive_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    app_archive_parser.add_argument("--comment", type=str, default="", help="Archive comment.")
    app_archive_parser.set_defaults(handler=_handle_application_archive)

    app_search_parser = application_subparsers.add_parser("search", help="Search applications.")
    app_search_parser.add_argument("query", type=str, help="Search query (company, title, note).")
    app_search_parser.add_argument("--limit", type=int, default=20, help="Limit (default: 20).")
    app_search_parser.set_defaults(handler=_handle_application_search)

    app_summarize_parser = application_subparsers.add_parser(
        "summarize", help="Summarize applications."
    )
    app_summarize_parser.set_defaults(handler=_handle_application_summarize)

    app_analytics_parser = application_subparsers.add_parser(
        "analytics", help="Application analytics and pipeline conversion rates."
    )
    app_analytics_parser.set_defaults(handler=_handle_application_analytics)

    app_reminder_parser = application_subparsers.add_parser(
        "reminder", help="Manage follow-up reminders."
    )
    app_reminder_subparsers = app_reminder_parser.add_subparsers(
        dest="application_reminder_command"
    )

    ar_add_parser = app_reminder_subparsers.add_parser("add", help="Schedule a follow-up reminder.")
    ar_add_parser.add_argument("application_id", type=int, help="Application ID.")
    ar_add_parser.add_argument("--due-days", type=int, default=None, help="Due in N days.")
    ar_add_parser.add_argument("--due-at", type=str, default=None, help="Due date (ISO datetime).")
    ar_add_parser.add_argument(
        "--message", type=str, default="Follow up on application", help="Reminder message."
    )
    ar_add_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    ar_add_parser.set_defaults(handler=_handle_application_reminder_add)

    ar_list_parser = app_reminder_subparsers.add_parser("list", help="List reminders.")
    ar_list_parser.add_argument("--status", type=str, default=None, help="Filter by status.")
    ar_list_parser.add_argument(
        "--due-before", type=str, default=None, help="Only reminders due before (ISO datetime)."
    )
    ar_list_parser.add_argument("--limit", type=int, default=50, help="Limit (default: 50).")
    ar_list_parser.set_defaults(handler=_handle_application_reminder_list)

    ar_complete_parser = app_reminder_subparsers.add_parser("complete", help="Complete a reminder.")
    ar_complete_parser.add_argument("reminder_id", type=int, help="Reminder ID.")
    ar_complete_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    ar_complete_parser.set_defaults(handler=_handle_application_reminder_complete)

    ar_snooze_parser = app_reminder_subparsers.add_parser("snooze", help="Snooze a reminder.")
    ar_snooze_parser.add_argument("reminder_id", type=int, help="Reminder ID.")
    ar_snooze_parser.add_argument(
        "--due-at", type=str, required=True, help="New due date (ISO datetime)."
    )
    ar_snooze_parser.add_argument("--actor", type=str, default="cli", help="Actor name.")
    ar_snooze_parser.set_defaults(handler=_handle_application_reminder_snooze)

    agent_parser = subparsers.add_parser(
        "agent", help="Chat with the StagePilot Career Agent."
    )
    agent_parser.add_argument(
        "--message",
        type=str,
        default=None,
        help="Process a single message and exit.",
    )
    agent_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full structured agent response as JSON.",
    )
    agent_parser.set_defaults(handler=_handle_agent)

    linkedin_parser = subparsers.add_parser(
        "linkedin", help="LinkedIn MCP pipeline commands."
    )
    linkedin_subparsers = linkedin_parser.add_subparsers(dest="linkedin_command")

    linkedin_match = linkedin_subparsers.add_parser(
        "match", help="Fetch + match LinkedIn jobs through the existing pipeline."
    )
    linkedin_match.add_argument(
        "--top",
        type=int,
        default=None,
        help="Limit the number of recommendations returned.",
    )
    linkedin_match.set_defaults(handler=_handle_linkedin_match)

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


def _handle_application_create(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        application = svc.create_from_approved_package(package_id=args.package_id, actor=args.actor)
    print(json.dumps(application.to_dict(), indent=2, default=str))
    return 0


def _handle_application_list(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        applications = svc.list_applications(
            status=args.status,
            company=args.company,
            label=args.label,
            date_from=args.date_from,
            date_to=args.date_to,
            limit=args.limit,
            offset=args.offset,
        )
        data = [a.to_dict() for a in applications]
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_application_show(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        application = svc.get_application(args.application_id)
        data = {
            "application": application.to_dict(),
            "timeline": [e.to_dict() for e in svc.get_timeline(args.application_id)],
            "history": [e.to_dict() for e in svc.get_history(args.application_id)],
            "notes": [n.to_dict() for n in svc.list_notes(args.application_id)],
            "reminders": [r.to_dict() for r in svc.list_reminders(limit=100)],
            "outcome": (
                svc.get_outcome(args.application_id).to_dict()
                if svc.get_outcome(args.application_id)
                else None
            ),
        }
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_application_update(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        application = svc.update_application(
            args.application_id,
            args.actor,
            company_name=args.company,
            job_title=args.job_title,
            resume_path=args.resume_path,
            cover_letter_path=args.cover_letter_path,
            comment=args.comment,
        )
        if args.labels is not None:
            labels = tuple(x.strip() for x in args.labels.split(",") if x.strip())
            application = svc.set_labels(args.application_id, labels, args.actor)
        if args.add_label:
            application = svc.add_label(args.application_id, args.add_label, args.actor)
        if args.remove_label:
            application = svc.remove_label(args.application_id, args.remove_label, args.actor)
        if args.note:
            svc.add_note(args.application_id, args.actor, args.note)
        if args.status:
            application = svc.change_status(
                args.application_id, args.status, args.actor, comment=args.comment
            )
    print(json.dumps(application.to_dict(), indent=2, default=str))
    return 0


def _handle_application_archive(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        application = svc.archive(args.application_id, args.actor, comment=args.comment)
    print(json.dumps(application.to_dict(), indent=2, default=str))
    return 0


def _handle_application_search(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        applications = svc.search_applications(args.query, limit=args.limit)
        data = [a.to_dict() for a in applications]
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_application_summarize(_args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        data = svc.summarize()
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_application_analytics(_args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        data = svc.analytics()
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_application_reminder_add(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        reminder = svc.schedule_follow_up(
            args.application_id,
            args.actor,
            due_at=args.due_at,
            due_days=args.due_days,
            message=args.message,
        )
    print(json.dumps(reminder.to_dict(), indent=2, default=str))
    return 0


def _handle_application_reminder_list(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        reminders = svc.list_reminders(
            status=args.status, due_before=args.due_before, limit=args.limit
        )
        data = [r.to_dict() for r in reminders]
    print(json.dumps(data, indent=2, default=str))
    return 0


def _handle_application_reminder_complete(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        reminder = svc.complete_reminder(args.reminder_id, args.actor)
    print(json.dumps(reminder.to_dict(), indent=2, default=str))
    return 0


def _handle_application_reminder_snooze(args: argparse.Namespace, settings: Settings) -> int:
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        svc = ApplicationService(session=session)
        reminder = svc.snooze_reminder(args.reminder_id, args.due_at, args.actor)
    print(json.dumps(reminder.to_dict(), indent=2, default=str))
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


def _handle_agent(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the agent command (single message or interactive REPL)."""
    from app.agent.agent import CareerAgent

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        agent = CareerAgent(session=session, settings=settings)

        if args.message:
            response = agent.handle(args.message)
            if args.json:
                print(json.dumps(response.to_dict(), indent=2, default=str))
            else:
                print(response.message)
            return 0 if response.success else 1

        print("StagePilot Career Agent. Type 'help' for capabilities, 'exit' to quit.")
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line.lower() in {"exit", "quit", "q"}:
                break
            response = agent.handle(line)
            session.commit()
            print(f"agent> {response.message}")
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _handle_discover(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the discovery command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        registry = build_connector_registry(settings)
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


_PROVIDER_SOURCE_TYPES = {
    "greenhouse": "greenhouse",
    "lever": "lever",
    "ashby": "ashby",
    "smart_recruiters": "smart_recruiters",
    "teamtailor": "teamtailor",
    "welcome_to_the_jungle": "welcome_to_the_jungle",
    "remote_ok": "remote_ok",
    "wellfound": "wellfound",
    "company_pages": "company_pages",
}


def _build_config(args: argparse.Namespace, *keys: str) -> dict[str, object]:
    """Build a provider config dict from CLI flags, skipping unset values."""
    config: dict[str, object] = {}
    for key in keys:
        value = getattr(args, key, None)
        if value is not None:
            config[key] = value
    extra = getattr(args, "config", None)
    if extra:
        config.update(json.loads(extra))
    return config


def _build_company_config(args: argparse.Namespace) -> dict[str, object]:
    """Build a company_pages config dict from CLI flags."""
    config: dict[str, object] = {
        "job_links_selector": args.selector,
        "scrape_details": not getattr(args, "no_scrape_details", False),
    }
    if args.list_url:
        config["list_url"] = args.list_url
    if args.next_selector:
        config["next_page_selector"] = args.next_selector
    if args.title_selector:
        config["title_selector"] = args.title_selector
    if args.description_selector:
        config["description_selector"] = args.description_selector
    config["max_pages"] = getattr(args, "max_pages", 1) or 1
    if args.company:
        config["company"] = args.company
    return config


def _handle_add_provider_source(
    args: argparse.Namespace,
    settings: Settings,
    provider_name: str,
    config: dict[str, object],
) -> int:
    """Handle the commands that add a provider-specific source."""
    source_type_name = _PROVIDER_SOURCE_TYPES[provider_name]
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        from app.domain.jobs.enums import JobSourceType

        source = JobSourceRepository(session).add_source(
            name=args.name,
            source_type=JobSourceType(source_type_name),
            base_url=args.url,
            config=config,
        )
        payload = {
            "id": source.id,
            "name": source.name,
            "type": source.type,
            "base_url": source.base_url,
            "config": source.config_json,
        }
    print(json.dumps(payload, sort_keys=True))
    return 0


def _handle_add_linkedin_mcp_source(args: argparse.Namespace, settings: Settings) -> int:
    """Handle adding a LinkedIn MCP server as a job source."""
    config: dict[str, object] = {"tool_name": args.tool}
    if args.args:
        config["server_args"] = _parse_mcp_args_value(args.args)
    if args.env:
        config["server_env"] = json.loads(args.env)
    if args.cwd:
        config["server_cwd"] = args.cwd
    if args.keywords:
        config["keywords"] = args.keywords
    if args.location:
        config["location"] = args.location
    if args.job_type:
        config["job_type"] = args.job_type
    if args.limit is not None:
        config["limit"] = args.limit
    if args.timeout is not None:
        config["timeout_seconds"] = args.timeout

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        from app.domain.jobs.enums import JobSourceType

        source = JobSourceRepository(session).add_source(
            name=args.name,
            source_type=JobSourceType.LINKEDIN_MCP,
            base_url=args.command,
            config=config,
        )
        payload = {
            "id": source.id,
            "name": source.name,
            "type": source.type,
            "base_url": source.base_url,
            "config": source.config_json,
        }
    print(json.dumps(payload, sort_keys=True))
    return 0


def _handle_linkedin_match(args: argparse.Namespace, settings: Settings) -> int:
    """Fetch and match LinkedIn MCP jobs through the existing pipeline."""
    from app.services.linkedin_mcp_pipeline_service import LinkedInMCPPipelineService

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = LinkedInMCPPipelineService(session=session, settings=settings)
        result = service.run(top_n=args.top)

    print(json.dumps(result.to_dict(), sort_keys=True, default=str))
    return 0


def _parse_mcp_args_value(value: str) -> list[str] | str:
    """Parse the MCP --args value as a JSON list or pass it through."""
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else value
    except (ValueError, TypeError):
        return value


def _resolve_source_id(args: argparse.Namespace, repo: JobSourceRepository) -> int | None:
    """Resolve a source ID from --id or --name flags."""
    if getattr(args, "id", None) is not None:
        return int(args.id)
    name = getattr(args, "name", None)
    if name:
        source = repo.get_source_by_name(name)
        if source is not None:
            return source.id
    return None


def _handle_remove_source(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the sources remove command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        repo = JobSourceRepository(session)
        source_id = _resolve_source_id(args, repo)
        if source_id is None:
            print(json.dumps({"error": "source --id or --name is required"}))
            return 1
        removed = repo.remove_source(source_id)
        payload = {"removed": removed, "source_id": source_id}
    print(json.dumps(payload, sort_keys=True))
    return 0 if removed else 1


def _handle_set_source_active(args: argparse.Namespace, settings: Settings, is_active: bool) -> int:
    """Handle the sources enable/disable commands."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        repo = JobSourceRepository(session)
        source_id = _resolve_source_id(args, repo)
        if source_id is None:
            print(json.dumps({"error": "source --id or --name is required"}))
            return 1
        source = repo.set_source_active(source_id, is_active)
        payload = {
            "id": source.id,
            "name": source.name,
            "is_active": source.is_active,
        }
    print(json.dumps(payload, sort_keys=True))
    return 0


def _handle_refresh_source(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the sources refresh command."""
    from app.domain.jobs.entities import JobSourceConfig
    from app.domain.jobs.enums import JobSourceType
    from app.services.discovery_service import DiscoveryService
    from app.services.duplicate_detection_service import DuplicateDetectionService
    from app.services.filtering_service import HardFilterService
    from app.services.job_matching_service import JobMatchingService
    from app.services.job_normalization_service import JobNormalizationService

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        repo = JobSourceRepository(session)
        record = repo.get_source(args.id)
        config = JobSourceConfig(
            id=record.id,
            name=record.name,
            type=JobSourceType(record.type),
            base_url=record.base_url,
            config=record.config_json,
        )
        registry = build_connector_registry(settings)
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
        summary = service.run_source(config)
    print(json.dumps(asdict(summary), sort_keys=True))
    return 0


def _handle_source_health(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the sources health command."""
    from app.domain.jobs.entities import JobSourceConfig
    from app.domain.jobs.enums import JobSourceType

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        repo = JobSourceRepository(session)
        record = repo.get_source(args.id)
        config = JobSourceConfig(
            id=record.id,
            name=record.name,
            type=JobSourceType(record.type),
            base_url=record.base_url,
            config=record.config_json,
        )
        registry = build_connector_registry(settings)
        connector = registry.get(config.type)
        health = connector.health(config)
        payload = {
            "provider": health.provider,
            "status": health.status,
            "latency_ms": health.latency_ms,
            "message": health.message,
        }
    print(json.dumps(payload, sort_keys=True))
    return 0 if health.status == "healthy" else 1


def _handle_test_source(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the sources test command (validate + dry-run fetch)."""
    from app.domain.jobs.entities import JobSourceConfig
    from app.domain.jobs.enums import JobSourceType

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        repo = JobSourceRepository(session)
        record = repo.get_source(args.id)
        config = JobSourceConfig(
            id=record.id,
            name=record.name,
            type=JobSourceType(record.type),
            base_url=record.base_url,
            config=record.config_json,
        )
        registry = build_connector_registry(settings)
        connector = registry.get(config.type)
        errors = connector.validate(config)
        payload: dict[str, object] = {
            "source_id": record.id,
            "name": record.name,
            "provider": connector.provider_name_value(),
            "valid": not errors,
            "errors": errors,
        }
        if not errors:
            jobs = connector.fetch(config)
            payload["fetched_count"] = len(jobs)
            payload["sample_titles"] = [j.title for j in jobs[:5]]
    print(json.dumps(payload, sort_keys=True))
    return 0 if not errors else 1


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


def _format_profile_validation_errors(errors: list[ProfileValidationIssue]) -> str:
    """Format structured profile validation errors for the CLI output."""
    lines: list[str] = ["Profile validation failed.", ""]
    for index, error in enumerate(errors, start=1):
        if index > 1:
            lines.append("")
        lines.append(f"{index}.")
        lines.append(f"Field: {error.field}")
        lines.append(f"Reason: {error.message}")
        if error.value is not None:
            lines.append(f"Value: {error.value}")
    return "\n".join(lines)


def _handle_profile_import(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile import command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = ProfileService(
            session=session,
            parser=detect_parser(args.file),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        file_path = Path(args.file)
        if not file_path.exists():
            print(json.dumps({"error": f"File not found: {file_path}"}))
            return 1
        try:
            profile = service.import_resume(file_path, description=args.description)
        except ProfileValidationError as exc:
            print(_format_profile_validation_errors(exc.errors))
            return 1
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
            data["personal_info"] = pii_utils.mask_profile_dict(data["personal_info"])
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


def _handle_profile_edit(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile edit command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        service = ProfileService(
            session=session,
            parser=PDFParser(),
            normalizer=ProfileNormalizer(),
            validator=ProfileValidator(),
        )
        profile_id = args.profile_id
        if profile_id is None:
            try:
                service.get_current_profile()
                active_id = session.scalar(
                    select(Profile.id).where(Profile.active.is_(True)).limit(1)
                )
                profile_id = active_id
            except Exception as exc:
                print(json.dumps({"error": f"No active profile: {exc}"}))
                return 1

        try:
            service.edit_profile(
                profile_id=profile_id,
                name=args.name,
                summary=args.summary,
            )
            result = {"status": "updated", "profile_id": profile_id}
        except Exception as exc:
            result = {"error": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return 0


def _handle_profile_validate(_args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile validate command."""
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
            errors = service.validate_profile()
            if errors:
                result = {
                    "valid": False,
                    "errors": [str(e) for e in errors],
                    "error_count": len(errors),
                }
            else:
                completeness = service.get_completeness()
                result = {
                    "valid": True,
                    "completeness_score": completeness.score,
                    "completeness_breakdown": completeness.breakdown,
                    "missing_fields": list(completeness.missing_fields),
                }
        except Exception as exc:
            result = {"error": str(exc)}
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


def _handle_profile_activate(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile activate command."""
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
            name = service.activate_profile(args.profile_id)
            result = {"status": "activated", "name": name}
        except Exception as exc:
            result = {"error": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return 0


def _handle_profile_list(_args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile list command."""
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
            profiles = service.list_profiles()
            masked = [pii_utils.mask_profile_dict(dict(p)) for p in profiles]
        except Exception as exc:
            masked = [{"error": str(exc)}]
    print(json.dumps(masked, sort_keys=True, indent=2))
    return 0


def _handle_profile_delete(args: argparse.Namespace, settings: Settings) -> int:
    """Handle the profile delete command."""
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
            service.delete_profile(args.profile_id)
            result = {"status": "deleted", "profile_id": args.profile_id}
        except Exception as exc:
            result = {"error": str(exc)}
    print(json.dumps(result, sort_keys=True))
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


def _handle_sources_benchmark(_args: argparse.Namespace, settings: Settings) -> int:
    """Handle the sources benchmark command.

    Runs the connector validation benchmark for every configured source and
    prints a health report with success rate, response time, normalization
    quality, duplicate rate, and error handling metrics.
    """
    from app.domain.jobs.entities import JobSourceConfig
    from app.domain.jobs.enums import JobSourceType

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        repo = JobSourceRepository(session)
        records = repo.list_sources()
        source_configs = [
            JobSourceConfig(
                id=record.id,
                name=record.name,
                type=JobSourceType(record.type),
                base_url=record.base_url,
                config=record.config_json,
            )
            for record in records
        ]
        registry = build_connector_registry(settings)
        service = SourceValidationService(settings=settings, registry=registry)
        report = service.benchmark_sources(source_configs)

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True, default=str))
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
        print(
            f"{'Rank':<6}{'Score':<8}{'Confidence':<12}{'Job ID':<8}"
            f"{'Status':<12}{'Matched Skills'}"
        )
        print("-" * 96)
        for rec in output:
            matched = ", ".join(rec["matched_detail"]["matched_skills"][:5])
            if len(rec["matched_detail"]["matched_skills"]) > 5:
                matched += "..."
            confidence = (
                rec.get("insights", {}).get("confidence", "n/a") if rec.get("insights") else "n/a"
            )
            print(
                f"{rec['ranking_position']:<6}"
                f"{rec['final_score']:<8.1f}"
                f"{confidence:<12}"
                f"{rec['job_id']:<8}"
                f"{rec['status']:<12}"
                f"{matched}"
            )
            if rec.get("insights") and rec["insights"].get("summary"):
                print(f"    Why: {rec['insights']['summary']}")
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
