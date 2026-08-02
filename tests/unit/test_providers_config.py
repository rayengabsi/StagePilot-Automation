from __future__ import annotations

from app.config.providers_config import ProvidersConfig, get_providers_config


def test_providers_config_loads_all_enabled_providers() -> None:
    """The providers.toml should list every supported provider."""
    config = get_providers_config()

    assert "rss" in config.enabled
    assert "greenhouse" in config.enabled
    assert "lever" in config.enabled
    assert "ashby" in config.enabled
    assert "smart_recruiters" in config.enabled
    assert "teamtailor" in config.enabled
    assert "welcome_to_the_jungle" in config.enabled
    assert "remote_ok" in config.enabled
    assert "wellfound" in config.enabled
    assert "company_pages" in config.enabled


def test_providers_config_is_enabled() -> None:
    """is_enabled should reflect the enabled list and section flags."""
    config = get_providers_config()

    assert config.is_enabled("greenhouse") is True
    assert config.is_enabled("does_not_exist") is False


def test_providers_config_for_provider_falls_back_to_defaults() -> None:
    """Unknown providers should fall back to the defaults section."""
    config = ProvidersConfig.load()

    provider = config.for_provider("made_up_provider")

    assert provider.name == "made_up_provider"
    assert provider.timeout_seconds == config.defaults.timeout_seconds


def test_requests_per_minute_never_zero() -> None:
    """The requests-per-minute budget should always be positive."""
    config = get_providers_config()

    assert config.for_provider("remote_ok").requests_per_minute >= 1
