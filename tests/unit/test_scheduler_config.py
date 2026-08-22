"""Tests for scheduler configuration loading and validation."""

from __future__ import annotations

import pytest
from app.config.scheduler_config import (
    SchedulerConfig,
    SchedulerConfigError,
    get_scheduler_config,
)


def test_defaults_disable_the_scheduler_with_thirty_minutes() -> None:
    config = SchedulerConfig.from_dict({})

    assert config.enabled is False
    assert config.interval_minutes == 30


def test_custom_values_are_parsed() -> None:
    config = SchedulerConfig.from_dict({"scheduler": {"enabled": True, "interval_minutes": 15}})

    assert config.enabled is True
    assert config.interval_minutes == 15


@pytest.mark.parametrize("bad_interval", [0, -5, "ten", 1.5, None, True])
def test_invalid_interval_raises(bad_interval: object) -> None:
    with pytest.raises(SchedulerConfigError):
        SchedulerConfig.from_dict({"scheduler": {"interval_minutes": bad_interval}})


@pytest.mark.parametrize("bad_enabled", ["yes", 1, None])
def test_invalid_enabled_raises(bad_enabled: object) -> None:
    with pytest.raises(SchedulerConfigError):
        SchedulerConfig.from_dict({"scheduler": {"enabled": bad_enabled}})


def test_getter_loads_toml_file(tmp_path: pytest.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "scheduler.toml").write_text(
        "[scheduler]\nenabled = true\ninterval_minutes = 45\n", encoding="utf-8"
    )
    get_scheduler_config.cache_clear()
    try:
        config = get_scheduler_config()
    finally:
        get_scheduler_config.cache_clear()

    assert config.enabled is True
    assert config.interval_minutes == 45


def test_getter_falls_back_to_defaults_without_file(
    tmp_path: pytest.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    get_scheduler_config.cache_clear()
    try:
        config = get_scheduler_config()
    finally:
        get_scheduler_config.cache_clear()

    assert config.enabled is False
    assert config.interval_minutes == 30
