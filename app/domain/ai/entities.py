from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.ai.enums import AIFeature


@dataclass(frozen=True, slots=True)
class AIResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class TokenUsage:
    provider: str
    model: str
    feature: AIFeature
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost: float = 0.0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "feature": self.feature.value,
            "prompt_version": self.prompt_version,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "estimated_cost": self.estimated_cost,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    explanation: str
    recommendation_id: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "explanation": self.explanation,
            "recommendation_id": self.recommendation_id,
        }


@dataclass(frozen=True, slots=True)
class TailoredResume:
    sections: dict[str, str]
    source_profile_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": self.sections,
            "source_profile_version": self.source_profile_version,
        }


@dataclass(frozen=True, slots=True)
class CoverLetter:
    body: str
    recipient_name: str | None = None
    company_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "body": self.body,
            "recipient_name": self.recipient_name,
            "company_name": self.company_name,
        }


@dataclass(frozen=True, slots=True)
class EmailDraft:
    subject: str
    body: str
    recipient: str | None = None
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "body": self.body,
            "recipient": self.recipient,
            "signature": self.signature,
        }
