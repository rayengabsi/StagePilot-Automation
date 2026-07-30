from __future__ import annotations

from typing import Protocol

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import ConnectorNotFoundError


class JobSourceConnector(Protocol):
    """Protocol implemented by all external job source connectors."""

    source_type: JobSourceType

    def fetch(self, source: JobSourceConfig) -> list[DiscoveredJob]:
        """Fetch discovered jobs from a configured source."""


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
