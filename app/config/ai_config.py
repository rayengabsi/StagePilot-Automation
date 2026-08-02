from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

AI_CONFIG_PATH = Path(__file__).parent / "ai.toml"


@dataclass(frozen=True, slots=True)
class AIProviderConfig:
    name: str
    model: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: int
    retry_count: int


@dataclass(frozen=True, slots=True)
class AIFeaturesConfig:
    explanations: bool
    resume_tailoring: bool
    cover_letter: bool
    email_draft: bool


@dataclass(frozen=True, slots=True)
class TailoringQualityConfig:
    enabled: bool
    minimum_quality_score: float


@dataclass(frozen=True, slots=True)
class AIConfig:
    provider: AIProviderConfig
    features: AIFeaturesConfig
    tailoring_quality: TailoringQualityConfig

    @classmethod
    def load(cls, path: Path = AI_CONFIG_PATH) -> AIConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        prov = raw["provider"]
        feat = raw["features"]
        quality = raw.get("tailoring_quality", {})
        return cls(
            provider=AIProviderConfig(
                name=prov["name"],
                model=prov["model"],
                temperature=float(prov["temperature"]),
                max_output_tokens=int(prov["max_output_tokens"]),
                timeout_seconds=int(prov["timeout_seconds"]),
                retry_count=int(prov["retry_count"]),
            ),
            features=AIFeaturesConfig(
                explanations=bool(feat["explanations"]),
                resume_tailoring=bool(feat["resume_tailoring"]),
                cover_letter=bool(feat["cover_letter"]),
                email_draft=bool(feat["email_draft"]),
            ),
            tailoring_quality=TailoringQualityConfig(
                enabled=bool(quality.get("enabled", True)),
                minimum_quality_score=float(quality.get("minimum_quality_score", 60.0)),
            ),
        )


@lru_cache(maxsize=1)
def get_ai_config(path: Path = AI_CONFIG_PATH) -> AIConfig:
    """Return cached AI configuration from ai.toml."""
    return AIConfig.load(path)
