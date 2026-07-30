from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from app.config.logging import configure_logging
from app.config.settings import Settings, get_settings
from app.db.session import create_database_engine, create_session_factory, session_scope
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector
from app.services.discovery_service import DiscoveryService
from app.services.job_normalization_service import JobNormalizationService
from app.services.job_source_repository import JobSourceRepository


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
    discover_parser.set_defaults(handler=_handle_discover)

    sources_parser = subparsers.add_parser("sources", help="Manage job sources.")
    sources_subparsers = sources_parser.add_subparsers(dest="sources_command")

    add_rss_parser = sources_subparsers.add_parser("add-rss", help="Add an RSS/Atom job source.")
    add_rss_parser.add_argument("--name", required=True, help="Unique source name.")
    add_rss_parser.add_argument("--url", required=True, help="RSS or Atom feed URL.")
    add_rss_parser.set_defaults(handler=_handle_add_rss_source)

    list_parser = sources_subparsers.add_parser("list", help="List configured job sources.")
    list_parser.set_defaults(handler=_handle_list_sources)

    return parser


def _handle_discover(_args: argparse.Namespace, settings: Settings) -> int:
    """Handle the discovery command."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    with session_scope(session_factory) as session:
        registry = ConnectorRegistry([RssFeedConnector(settings)])
        service = DiscoveryService(
            session=session,
            connector_registry=registry,
            normalizer=JobNormalizationService(),
        )
        summary = service.run_once()

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
