from __future__ import annotations

from sqlalchemy.orm import Session

from app.config.ai_config import AIConfig
from app.config.settings import Settings
from app.domain.ai.enums import AIFeature
from app.domain.ai.errors import AIError, ConfigurationError, ProviderError
from app.infrastructure.ai.abstract import AIProvider
from app.infrastructure.ai.gemini_provider import GeminiProvider
from app.services.output_validator import OutputValidator
from app.services.prompt_service import PromptService
from app.services.token_tracker import TokenTracker


class AIOrchestrator:
    """Orchestrate AI operations: load prompt, call provider, validate, track usage.

    This is the single entry point for all AI features.
    It does NOT perform any business logic or matching decisions.
    """

    def __init__(
        self,
        ai_config: AIConfig,
        settings: Settings,
        session: Session,
        prompt_service: PromptService | None = None,
        provider: AIProvider | None = None,
        validator: OutputValidator | None = None,
        token_tracker: TokenTracker | None = None,
    ) -> None:
        self._config = ai_config
        self._settings = settings
        self._prompt_service = prompt_service or PromptService()
        self._provider = provider or self._build_provider()
        self._validator = validator or OutputValidator()
        self._token_tracker = token_tracker or TokenTracker(session)

    def generate_text(
        self,
        prompt_name: str,
        variables: dict[str, str],
        feature: AIFeature,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text: load prompt → render → call provider → validate → track → return."""
        rendered = self._prompt_service.render(prompt_name, variables)
        prompt_version = self._prompt_service.get_version(prompt_name)

        kwargs: dict[str, object] = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens

        try:
            response = self._provider.generate(rendered, **kwargs)
        except ProviderError:
            raise
        except Exception as exc:
            raise AIError(f"AI generation failed: {exc}") from exc

        self._validator.validate_text(response.text)

        self._token_tracker.track(
            provider=response.provider,
            model=response.model,
            feature=feature,
            prompt_version=prompt_version,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
        )

        return response.text

    def generate_json(
        self,
        prompt_name: str,
        variables: dict[str, str],
        feature: AIFeature,
        required_fields: list[str],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, object]:
        """Generate JSON: same pipeline as generate_text + JSON validation."""
        text = self.generate_text(
            prompt_name=prompt_name,
            variables=variables,
            feature=feature,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._validator.validate_json(text, required_fields)

    def _build_provider(self) -> AIProvider:
        cfg = self._config.provider
        if cfg.name == "gemini":
            return GeminiProvider(cfg, self._settings)
        raise ConfigurationError(f"Unsupported AI provider: {cfg.name}")
