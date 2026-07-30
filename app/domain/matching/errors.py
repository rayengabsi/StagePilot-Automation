from __future__ import annotations

from app.domain.jobs.errors import DiscoveryError


class FilteringError(DiscoveryError):
    """Base exception for hard-filter failures."""


class DuplicateDetectionError(DiscoveryError):
    """Base exception for duplicate-detection failures."""
