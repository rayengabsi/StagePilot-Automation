from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


class SchedulerConfigError(ValueError):
    """Raised when the scheduler configuration is invalid."""


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    """Configuration for the automated pipeline scheduler."""

    enabled: bool = False
    interval_minutes: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchedulerConfig:
        scheduler = data.get("scheduler", {})
        enabled = scheduler.get("enabled", False)
        interval = scheduler.get("interval_minutes", 30)
        if not isinstance(enabled, bool):
            raise SchedulerConfigError(f"scheduler.enabled must be a boolean, got {enabled!r}")
        if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1:
            raise SchedulerConfigError(
                f"scheduler.interval_minutes must be an integer >= 1, got {interval!r}"
            )
        return cls(enabled=enabled, interval_minutes=interval)


@lru_cache
def get_scheduler_config() -> SchedulerConfig:
    """Load scheduler configuration from config/scheduler.toml."""
    config_path = Path("config/scheduler.toml")
    if config_path.exists():
        raw = config_path.read_text(encoding="utf-8")
        data: dict[str, Any] = tomllib.loads(raw)
        return SchedulerConfig.from_dict(data)
    return SchedulerConfig()
