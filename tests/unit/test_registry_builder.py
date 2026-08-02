from __future__ import annotations

import pytest
from app.config.providers_config import ProvidersConfig
from app.config.settings import Settings
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.registry import (
    build_connector_registry,
    get_connector_class,
)
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector


def test_build_connector_registry_registers_enabled_providers() -> None:
    """The registry builder should register every globally enabled provider."""
    registry = build_connector_registry(Settings())

    for source_type in (
        JobSourceType.RSS_FEED,
        JobSourceType.GREENHOUSE,
        JobSourceType.LEVER,
        JobSourceType.ASHBY,
        JobSourceType.SMART_RECRUITERS,
        JobSourceType.TEAMTAILOR,
        JobSourceType.WELCOME_TO_THE_JUNGLE,
        JobSourceType.REMOTE_OK,
        JobSourceType.WELLFOUND,
        JobSourceType.COMPANY_PAGES,
    ):
        assert registry.get(source_type) is not None


def test_build_connector_registry_respects_disabled_providers() -> None:
    """Disabled providers should be excluded from the registry."""
    loaded = ProvidersConfig.load()
    config = ProvidersConfig(
        enabled=("rss",),
        providers=loaded.providers,
        defaults=loaded.defaults,
    )
    registry = build_connector_registry(Settings(), config=config)

    assert set(registry._connectors.keys()) == {JobSourceType.RSS_FEED}


def test_get_connector_class_maps_provider_names() -> None:
    """Connector classes should be resolvable by provider name."""
    cls = get_connector_class("rss")

    assert cls is RssFeedConnector


def test_get_connector_class_raises_for_unknown_provider() -> None:
    """Unknown provider names should raise a clear error."""
    from app.domain.jobs.errors import ConnectorNotFoundError

    with pytest.raises(ConnectorNotFoundError):
        get_connector_class("not_a_provider")
