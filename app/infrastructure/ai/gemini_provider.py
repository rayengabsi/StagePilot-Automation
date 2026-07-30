from __future__ import annotations

import time

from google import genai

from app.config.ai_config import AIProviderConfig
from app.config.settings import Settings
from app.domain.ai.entities import AIResponse
from app.domain.ai.errors import ProviderError
from app.infrastructure.ai.abstract import AIProvider


class GeminiProvider(AIProvider):
    """AI provider using Google's Gemini API via the google-genai SDK."""

    def __init__(self, config: AIProviderConfig, settings: Settings) -> None:
        self._config = config
        api_key = settings.gemini_api_key
        if not api_key:
            raise ProviderError("Gemini API key is not configured")
        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, **kwargs: object) -> AIResponse:
        model = str(kwargs.get("model", self._config.model))
        temperature = float(kwargs.get("temperature", self._config.temperature))
        max_tokens = int(kwargs.get("max_output_tokens", self._config.max_output_tokens))

        start = time.monotonic()
        try:
            response = self._client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
        except Exception as exc:
            raise ProviderError(f"Gemini API call failed: {exc}") from exc

        elapsed = int((time.monotonic() - start) * 1000)
        text = response.text if hasattr(response, "text") and response.text else ""

        usage = getattr(response, "usage_metadata", None)
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        return AIResponse(
            text=text,
            provider="gemini",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=elapsed,
        )
