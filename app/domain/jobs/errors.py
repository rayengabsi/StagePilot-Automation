from __future__ import annotations


class DiscoveryError(Exception):
    """Base exception for job discovery failures."""


class ConnectorNotFoundError(DiscoveryError):
    """Raised when no connector is registered for a source type."""


class SourceFetchError(DiscoveryError):
    """Raised when a source cannot be fetched."""


class SourceParseError(DiscoveryError):
    """Raised when a source response cannot be parsed."""


class JobNormalizationError(DiscoveryError):
    """Raised when a discovered job cannot be normalized."""


class SourceConfigError(DiscoveryError):
    """Raised when a source is missing required configuration."""


class PaginationError(DiscoveryError):
    """Raised when a provider pagination response is malformed."""


class RateLimitExceededError(DiscoveryError):
    """Raised when a provider rate limit prevents further requests."""
