from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

MATCHING_CONFIG_PATH = Path(__file__).parent / "matching.toml"


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    weights: dict[str, float]
    thresholds: dict[str, float]
    hard_rules: dict[str, bool]
    fuzz_threshold: int

    @classmethod
    def load(cls, path: Path = MATCHING_CONFIG_PATH) -> MatchingConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(
            weights={k: float(v) for k, v in raw["weights"].items()},
            thresholds={k: float(v) for k, v in raw["thresholds"].items()},
            hard_rules={k: bool(v) for k, v in raw["hard_rules"].items()},
            fuzz_threshold=int(raw["similarity"]["fuzz_threshold"]),
        )


@lru_cache(maxsize=1)
def get_matching_config(path: Path = MATCHING_CONFIG_PATH) -> MatchingConfig:
    """Return cached matching configuration from matching.toml."""
    return MatchingConfig.load(path)
