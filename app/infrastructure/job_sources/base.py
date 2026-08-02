from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from app.config.providers_config import ProviderConfig, get_providers_config
from app.config.settings import Settings
from app.domain.jobs.entities import (
    DiscoveredJob,
    JobSourceConfig,
    ProviderHealth,
)
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.http.client import HttpClient
from app.infrastructure.job_sources.rate_limiter import RateLimiter
from app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class PageResult:
    """One page of raw provider items plus a cursor for the next page."""

    items: list[dict[str, Any]]
    next_cursor: Any = None


class BaseJobSourceConnector(ABC):
    """Abstract base for all job source connectors.

    Implements the shared discovery contract — ``fetch``, ``discover``,
    ``validate``, ``health``, and ``normalize`` — while delegating
    provider-specific request pagination and payload normalization to
    subclasses. All connectors reuse the same HttpClient and RateLimiter.
    """

    source_type: ClassVar[JobSourceType]
    provider_name: ClassVar[str]

    def __init__(
        self,
        settings: Settings,
        config: ProviderConfig | None = None,
        http_client: HttpClient | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Initialize the connector with shared HTTP and rate limiting infra."""
        self._settings = settings
        self._config = config or get_providers_config().for_provider(self.provider_name)
        self._http = http_client or HttpClient(settings, self._config)
        self._rate_limiter = rate_limiter or RateLimiter(self._config.min_interval_seconds)

    @classmethod
    def provider_name_value(cls) -> str:
        """Return the provider name for this connector class."""
        return cls.provider_name

    def fetch(self, source: JobSourceConfig) -> list[DiscoveredJob]:
        """Fetch all jobs from a source across all pages."""
        jobs: list[DiscoveredJob] = []
        cursor = self._initial_cursor(source)
        while True:
            self._rate_limiter.wait()
            page = self._fetch_page(source, cursor)
            for raw in page.items:
                job = self.normalize(raw, source)
                if job is not None:
                    jobs.append(job)
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
        return jobs

    def discover(self, source: JobSourceConfig) -> list[DiscoveredJob]:
        """Alias for fetch; kept for connector interface completeness."""
        return self.fetch(source)

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that a source has the required configuration."""
        errors: list[str] = []
        if not source.base_url or not source.base_url.strip():
            errors.append("base_url is required")
        return errors

    def health(self, source: JobSourceConfig) -> ProviderHealth:
        """Check provider connectivity and return a health result."""
        started = time.monotonic()
        try:
            self._http.get(self._health_url(source), headers=self._build_headers(source))
            latency = round((time.monotonic() - started) * 1000, 2)
            return ProviderHealth(
                provider=self.provider_name,
                status="healthy",
                latency_ms=latency,
                message="OK",
                checked_at=utc_now(),
            )
        except Exception as exc:
            latency = round((time.monotonic() - started) * 1000, 2)
            return ProviderHealth(
                provider=self.provider_name,
                status="unhealthy",
                latency_ms=latency,
                message=str(exc),
                checked_at=utc_now(),
            )

    @abstractmethod
    def normalize(self, raw: dict[str, Any], source: JobSourceConfig) -> DiscoveredJob | None:
        """Convert one raw provider payload into a discovered job."""

    @abstractmethod
    def _fetch_page(self, source: JobSourceConfig, cursor: Any) -> PageResult:  # noqa: ANN401
        """Fetch one page of raw provider items and return the next cursor."""

    def _initial_cursor(self, source: JobSourceConfig) -> Any:  # noqa: ANN401, ARG002
        """Return the cursor for the first page request."""
        return None

    def _build_headers(self, source: JobSourceConfig) -> dict[str, str]:  # noqa: ARG002
        """Return request headers for this provider."""
        return {}

    def _health_url(self, source: JobSourceConfig) -> str:
        """Return the URL used for health checks."""
        return source.base_url
