from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.ai.entities import AIResponse


class AIProvider(ABC):
    """Abstract interface for AI model providers.

    Implementations handle authentication, request formatting,
    response parsing, and error mapping for a specific provider.
    """

    @abstractmethod
    def generate(self, prompt: str, **kwargs: object) -> AIResponse:
        """Send a prompt to the AI model and return the response.

        Args:
            prompt: The full prompt text to send.
            **kwargs: Provider-specific overrides (model, temperature, etc.).

        Returns:
            AIResponse with generated text and usage metadata.

        Raises:
            ProviderError: On network, auth, rate-limit, or API errors.
        """
