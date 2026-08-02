from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.jobs.enums import JobSourceType


@dataclass(frozen=True, slots=True)
class JobSourceConfig:
    """Configuration for one external job source."""

    id: int
    name: str
    type: JobSourceType
    base_url: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiscoveredJob:
    """Job listing discovered by an external source connector."""

    external_id: str | None
    url: str
    title: str
    company: str | None
    location: str | None
    description: str | None
    raw_payload: dict[str, Any]
    discovered_at: datetime
    posted_at: datetime | None = None
    department: str | None = None
    employment_type: str | None = None
    remote_status: str | None = None
    requirements: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedJob:
    """Canonical normalized job data ready for persistence."""

    external_id: str | None
    url: str
    title: str
    company: str | None
    location: str | None
    description: str | None
    requirements: str | None
    posted_at: datetime | None
    department: str | None = None
    employment_type: str | None = None
    remote_status: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Result of a provider connectivity health check."""

    provider: str
    status: str
    latency_ms: float
    message: str
    checked_at: datetime
