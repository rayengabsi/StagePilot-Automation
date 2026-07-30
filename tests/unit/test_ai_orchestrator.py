from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.config.ai_config import AIConfig, AIFeaturesConfig, AIProviderConfig
from app.config.settings import Settings
from app.domain.ai.entities import AIResponse
from app.domain.ai.enums import AIFeature
from app.domain.ai.errors import ConfigurationError, ProviderError, ValidationError
from app.services.ai_orchestrator import AIOrchestrator
from app.services.output_validator import OutputValidator


@pytest.fixture
def ai_config() -> AIConfig:
    return AIConfig(
        provider=AIProviderConfig(
            name="gemini", model="gemini-2.0-flash-lite",
            temperature=0.7, max_output_tokens=1024,
            timeout_seconds=30, retry_count=2,
        ),
        features=AIFeaturesConfig(
            explanations=True, resume_tailoring=True,
            cover_letter=True, email_draft=True,
        ),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(gemini_api_key="test-key")


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.generate.return_value = AIResponse(
        text="This is a valid generated text with sufficient length.",
        provider="gemini",
        model="gemini-2.0-flash-lite",
        input_tokens=50,
        output_tokens=20,
        latency_ms=200,
    )
    return provider


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


def test_generate_text_success(
    ai_config: AIConfig, settings: Settings,
    mock_provider: MagicMock, mock_session: MagicMock,
) -> None:
    orchestrator = AIOrchestrator(
        ai_config=ai_config, settings=settings, session=mock_session,
        provider=mock_provider,
    )
    text = orchestrator.generate_text(
        prompt_name="match_explanation",
        variables={"job_title": "Engineer", "company": "Acme", "final_score": "85.0",
                    "matched_skills": "Python", "missing_skills": "Docker",
                    "matched_technologies": "", "missing_technologies": "",
                    "score_breakdown": "{}", "hard_rule_result": "passed"},
        feature=AIFeature.EXPLANATION,
    )
    assert "valid generated text" in text
    mock_provider.generate.assert_called_once()


def test_generate_text_provider_error(
    ai_config: AIConfig, settings: Settings,
    mock_provider: MagicMock, mock_session: MagicMock,
) -> None:
    mock_provider.generate.side_effect = ProviderError("API error")
    orchestrator = AIOrchestrator(
        ai_config=ai_config, settings=settings, session=mock_session,
        provider=mock_provider,
    )
    with pytest.raises(ProviderError, match="API error"):
        orchestrator.generate_text(
            prompt_name="match_explanation",
            variables={"job_title": "", "company": "", "final_score": "0",
                        "matched_skills": "", "missing_skills": "",
                        "matched_technologies": "", "missing_technologies": "",
                        "score_breakdown": "{}", "hard_rule_result": "passed"},
            feature=AIFeature.EXPLANATION,
        )


def test_generate_text_validation_failure(
    ai_config: AIConfig, settings: Settings,
    mock_provider: MagicMock, mock_session: MagicMock,
) -> None:
    mock_provider.generate.return_value = AIResponse(
        text="short", provider="gemini", model="gemini-2.0-flash-lite",
    )
    validator = OutputValidator()
    orchestrator = AIOrchestrator(
        ai_config=ai_config, settings=settings, session=mock_session,
        provider=mock_provider, validator=validator,
    )
    with pytest.raises(ValidationError, match="too short"):
        orchestrator.generate_text(
            prompt_name="match_explanation",
            variables={"job_title": "", "company": "", "final_score": "0",
                        "matched_skills": "", "missing_skills": "",
                        "matched_technologies": "", "missing_technologies": "",
                        "score_breakdown": "{}", "hard_rule_result": "passed"},
            feature=AIFeature.EXPLANATION,
        )


def test_generate_json_success(
    ai_config: AIConfig, settings: Settings,
    mock_provider: MagicMock, mock_session: MagicMock,
) -> None:
    mock_provider.generate.return_value = AIResponse(
        text='{"summary": "Great fit", "skills": "Python"}',
        provider="gemini", model="gemini-2.0-flash-lite",
        input_tokens=50, output_tokens=30, latency_ms=300,
    )
    orchestrator = AIOrchestrator(
        ai_config=ai_config, settings=settings, session=mock_session,
        provider=mock_provider,
    )
    data = orchestrator.generate_json(
        prompt_name="resume_tailoring",
        variables={"profile_json": "{}", "job_title": "Engineer",
                    "job_description": "", "matched_skills": "",
                    "missing_skills": ""},
        feature=AIFeature.RESUME_TAILORING,
        required_fields=["summary", "skills"],
    )
    assert data["summary"] == "Great fit"
    assert data["skills"] == "Python"


def test_generate_json_missing_field(
    ai_config: AIConfig, settings: Settings,
    mock_provider: MagicMock, mock_session: MagicMock,
) -> None:
    mock_provider.generate.return_value = AIResponse(
        text='{"summary": "Great fit"}',
        provider="gemini", model="gemini-2.0-flash-lite",
    )
    orchestrator = AIOrchestrator(
        ai_config=ai_config, settings=settings, session=mock_session,
        provider=mock_provider,
    )
    with pytest.raises(ValidationError, match="missing required field"):
        orchestrator.generate_json(
            prompt_name="resume_tailoring",
            variables={"profile_json": "{}", "job_title": "",
                        "job_description": "", "matched_skills": "",
                        "missing_skills": ""},
            feature=AIFeature.RESUME_TAILORING,
            required_fields=["summary", "skills"],
        )


def test_orchestrator_rejects_unsupported_provider(mock_session: MagicMock) -> None:
    config = AIConfig(
        provider=AIProviderConfig(
            name="nonexistent", model="x", temperature=0.5,
            max_output_tokens=100, timeout_seconds=10, retry_count=0,
        ),
        features=AIFeaturesConfig(
            explanations=True, resume_tailoring=True,
            cover_letter=True, email_draft=True,
        ),
    )
    settings = Settings(gemini_api_key="test-key")
    with pytest.raises(ConfigurationError, match="nonexistent"):
        AIOrchestrator(ai_config=config, settings=settings, session=mock_session)
