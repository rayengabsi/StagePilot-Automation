from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    """Configuration for the application execution engine."""

    reminders_enabled: bool = True
    follow_up_default_days: int = 3
    default_labels: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplicationConfig:
        reminders = data.get("reminders", {})
        labels = data.get("labels", {})
        return cls(
            reminders_enabled=reminders.get("enabled", True),
            follow_up_default_days=reminders.get("default_days", 3),
            default_labels=tuple(labels.get("default", [])),
        )


@lru_cache
def get_application_config() -> ApplicationConfig:
    """Load application configuration from config/application.toml."""
    config_path = Path("config/application.toml")
    if config_path.exists():
        raw = config_path.read_text(encoding="utf-8")
        data: dict[str, Any] = tomllib.loads(raw)
        return ApplicationConfig.from_dict(data)
    return ApplicationConfig()
