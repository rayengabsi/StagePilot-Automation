from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CLASSIFICATION_CONFIG_PATH = Path(__file__).parent / "classification.toml"


@dataclass(frozen=True, slots=True)
class ClassificationConfig:
    """Keyword dictionaries and scoring rules for job classification."""

    title_weight: float
    body_weight: float
    min_score: float
    specializations: dict[str, tuple[str, ...]]
    seniority_levels: dict[str, tuple[str, ...]]
    employment_types: dict[str, tuple[str, ...]]
    work_modes: dict[str, tuple[str, ...]]
    urgency: tuple[str, ...]

    @classmethod
    def load(cls, path: Path = CLASSIFICATION_CONFIG_PATH) -> ClassificationConfig:
        """Load classification dictionaries from a TOML file."""
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        scoring = raw["scoring"]
        return cls(
            title_weight=float(scoring["title_weight"]),
            body_weight=float(scoring["body_weight"]),
            min_score=float(scoring["min_score"]),
            specializations={
                name: tuple(keywords) for name, keywords in raw["specializations"].items()
            },
            seniority_levels={
                name: tuple(keywords) for name, keywords in raw["seniority_levels"].items()
            },
            employment_types={
                name: tuple(keywords) for name, keywords in raw["employment_types"].items()
            },
            work_modes={name: tuple(keywords) for name, keywords in raw["work_modes"].items()},
            urgency=tuple(raw["urgency"]["urgent"]),
        )


@lru_cache(maxsize=1)
def get_classification_config(path: Path = CLASSIFICATION_CONFIG_PATH) -> ClassificationConfig:
    """Return the cached classification configuration."""
    return ClassificationConfig.load(path)
