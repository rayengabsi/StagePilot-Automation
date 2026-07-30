from __future__ import annotations

import pytest
from app.config.settings import Settings
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import ConnectorNotFoundError
from app.infrastructure.job_sources.registry import ConnectorRegistry
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector


def test_connector_registry_returns_registered_connector() -> None:
    """Registry should resolve connectors by source type."""
    connector = RssFeedConnector(Settings())
    registry = ConnectorRegistry([connector])

    assert registry.get(JobSourceType.RSS_FEED) is connector


def test_connector_registry_raises_for_missing_connector() -> None:
    """Registry should fail clearly when no connector is registered."""
    registry = ConnectorRegistry([])

    with pytest.raises(ConnectorNotFoundError):
        registry.get(JobSourceType.RSS_FEED)
