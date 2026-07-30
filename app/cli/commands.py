from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.config.logging import configure_logging
from app.config.settings import Settings, get_settings
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector
from app.infrastructure.parsers.pdf_parser import PDFParser
from app.services.discovery_service import DiscoveryService
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.filtering_service import HardFilterService
from app.services.job_matching_service import JobMatchingService
from app.services.job_normalization_service import JobNormalizationService
from app.services.job_source_repository import JobSourceRepository
from app.services.profile_normalizer import ProfileNormalizer
from app.services.profile_service import ProfileService
from app.services.profile_validator import ProfileValidator
from app.services.recommendation_service import RecommendationService


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
    recommend_parser.add_argument(
        "--json", action="store_true", help="Output raw JSON."
    )
    recommend_parser.add_argument(
        "--list", action="store_true", help="List persisted recommendations instead of running."
    )
    recommend_parser.set_defaults(handler=_handle_recommend)

    feedback_parser = subparsers.add_parser(
        "feedback", help="Submit feedback for a recommendation."
    )
    feedback_parser.add_argument(
        "recommendation_id", type=int, help="Recommendation record ID."
    )
    feedback_parser.add_argument(
        "--reason", required=True,
        choices=[
            "wrong_country", "wrong_field", "wrong_technologies",
            "too_senior", "salary", "not_remote", "other",
        ],
        help="Feedback reason.",
    )
    feedback_parser.add_argument(
        "--comment", type=str, default=None, help="Optional free text comment."
    )
    feedback_parser.set_defaults(handler=_handle_feedback)

    return parser


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
