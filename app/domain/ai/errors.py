from __future__ import annotations


class AIError(Exception):
    """Base error for AI operations."""


class ProviderError(AIError):
    """Error from the AI provider (network, auth, rate limit)."""


class ValidationError(AIError):
    """AI output failed validation."""


class ConfigurationError(AIError):
    """AI configuration is missing or invalid."""


class PromptError(AIError):
    """Prompt loading or rendering failed."""


class TokenTrackingError(AIError):
    """Token usage tracking failed."""
