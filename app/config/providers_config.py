from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROVIDERS_CONFIG_PATH = Path(__file__).parent / "providers.toml"


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Per-provider HTTP and rate limiting behavior."""

    name: str
    enabled: bool
    timeout_seconds: int
    retry_attempts: int
    min_interval_seconds: float
    rate_limit_per_minute: int
    base_headers: dict[str, str]

    @property
    def requests_per_minute(self) -> float:
        """Return the effective requests-per-minute budget."""
        return max(1.0, float(self.rate_limit_per_minute))


@dataclass(frozen=True, slots=True)
class ProvidersConfig:
    """Full provider configuration loaded from providers.toml."""

    enabled: tuple[str, ...]
    providers: dict[str, ProviderConfig]
    defaults: ProviderConfig

    def is_enabled(self, name: str) -> bool:
        """Return whether a named provider is globally enabled."""
        if name not in self.providers:
            return False
        return self.providers[name].enabled and name in self.enabled

    def for_provider(self, name: str) -> ProviderConfig:
        """Return the effective config for a provider, falling back to defaults."""
        configured = self.providers.get(name)
        if configured is not None:
            return configured
        return _replace_name(self.defaults, name)

    @classmethod
    def load(cls, path: Path = PROVIDERS_CONFIG_PATH) -> ProvidersConfig:
        """Load and parse providers.toml into a ProvidersConfig."""
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        defaults_raw = raw["defaults"]
        defaults = ProviderConfig(
            name="defaults",
            enabled=True,
            timeout_seconds=int(defaults_raw["timeout_seconds"]),
            retry_attempts=int(defaults_raw["retry_attempts"]),
            min_interval_seconds=float(defaults_raw["min_interval_seconds"]),
            rate_limit_per_minute=int(defaults_raw["rate_limit_per_minute"]),
            base_headers=dict(defaults_raw.get("base_headers", {})),
        )
        providers: dict[str, ProviderConfig] = {}
        for name, section in raw.get("providers", {}).items():
            if not isinstance(section, dict) or name == "enabled":
                continue
            providers[name] = ProviderConfig(
                name=name,
                enabled=bool(section.get("enabled", True)),
                timeout_seconds=int(section.get("timeout_seconds", defaults.timeout_seconds)),
                retry_attempts=int(section.get("retry_attempts", defaults.retry_attempts)),
                min_interval_seconds=float(
                    section.get("min_interval_seconds", defaults.min_interval_seconds)
                ),
                rate_limit_per_minute=int(
                    section.get("rate_limit_per_minute", defaults.rate_limit_per_minute)
                ),
                base_headers=dict(section.get("base_headers", {})),
            )
        enabled = tuple(str(name) for name in raw["providers"].get("enabled", []))
        return cls(enabled=enabled, providers=providers, defaults=defaults)


def _replace_name(config: ProviderConfig, name: str) -> ProviderConfig:
    """Return a copy of *config* with a different provider name."""
    return ProviderConfig(
        name=name,
        enabled=config.enabled,
        timeout_seconds=config.timeout_seconds,
        retry_attempts=config.retry_attempts,
        min_interval_seconds=config.min_interval_seconds,
        rate_limit_per_minute=config.rate_limit_per_minute,
        base_headers=dict(config.base_headers),
    )


@lru_cache(maxsize=1)
def get_providers_config(path: Path = PROVIDERS_CONFIG_PATH) -> ProvidersConfig:
    """Return cached provider configuration from providers.toml."""
    return ProvidersConfig.load(path)
