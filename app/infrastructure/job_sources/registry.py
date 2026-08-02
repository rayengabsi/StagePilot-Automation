from __future__ import annotations

from typing import Protocol

from app.config.providers_config import ProvidersConfig, get_providers_config
from app.config.settings import Settings
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import ConnectorNotFoundError
from app.infrastructure.job_sources.ashby_connector import AshbyConnector
from app.infrastructure.job_sources.base import BaseJobSourceConnector
from app.infrastructure.job_sources.company_pages_connector import CompanyPagesConnector
from app.infrastructure.job_sources.greenhouse_connector import GreenhouseConnector
from app.infrastructure.job_sources.lever_connector import LeverConnector
from app.infrastructure.job_sources.remote_ok_connector import RemoteOkConnector
from app.infrastructure.job_sources.rss_feed_connector import RssFeedConnector
from app.infrastructure.job_sources.smart_recruiters_connector import SmartRecruitersConnector
from app.infrastructure.job_sources.teamtailor_connector import TeamtailorConnector
from app.infrastructure.job_sources.welcome_to_the_jungle_connector import (
    WelcomeToTheJungleConnector,
)
from app.infrastructure.job_sources.wellfound_connector import WellfoundConnector


class JobSourceConnector(Protocol):
    """Protocol implemented by all external job source connectors."""

    source_type: JobSourceType

    def fetch(self, source: JobSourceConfig) -> list[DiscoveredJob]:
        """Fetch discovered jobs from a configured source."""


_ALL_CONNECTORS: tuple[type[BaseJobSourceConnector], ...] = (
    RssFeedConnector,
    GreenhouseConnector,
    LeverConnector,
    AshbyConnector,
    SmartRecruitersConnector,
    TeamtailorConnector,
    WelcomeToTheJungleConnector,
    RemoteOkConnector,
    WellfoundConnector,
    CompanyPagesConnector,
)


def get_connector_class(provider_name: str) -> type[BaseJobSourceConnector]:
    """Return the connector class registered for a provider name."""
    for connector_class in _ALL_CONNECTORS:
        if connector_class.provider_name == provider_name:
            return connector_class
    raise ConnectorNotFoundError(f"No connector class for provider: {provider_name}")


def build_connector_registry(
    settings: Settings,
    config: ProvidersConfig | None = None,
) -> ConnectorRegistry:
    """Build a registry of connectors for every globally enabled provider."""
    config = config or get_providers_config()
    connectors: list[BaseJobSourceConnector] = []
    for provider_name in config.enabled:
        if not config.is_enabled(provider_name):
            continue
        try:
            connector_class = get_connector_class(provider_name)
        except ConnectorNotFoundError:
            continue
        connectors.append(connector_class(settings, config=config.for_provider(provider_name)))
    return ConnectorRegistry(connectors)


class ConnectorRegistry:
    """Registry mapping source types to connector implementations."""

    def __init__(self, connectors: list[JobSourceConnector]) -> None:
        """Initialize the registry with connector implementations."""
        self._connectors = {connector.source_type: connector for connector in connectors}

    def get(self, source_type: JobSourceType) -> JobSourceConnector:
        """Return the connector registered for a source type."""
        connector = self._connectors.get(source_type)
        if connector is None:
            raise ConnectorNotFoundError(f"No connector registered for source type: {source_type}")
        return connector
