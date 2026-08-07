"""Unit tests for cross-platform LinkedIn MCP configuration.

These verify that the server location comes only from the TOML or environment
variables (never a machine-specific absolute path), and that bare executables
resolve through PATH on every OS.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.config.linkedin_mcp_config import (
    LINKEDIN_MCP_CONFIG_PATH,
    LinkedInMCPConfig,
    _resolve_command,
)


def test_default_command_is_cross_platform_bare_executable() -> None:
    config = LinkedInMCPConfig.load(LINKEDIN_MCP_CONFIG_PATH)
    assert config.command == "python"
    assert not os.path.isabs(config.command)


def test_default_cwd_is_repository_relative() -> None:
    config = LinkedInMCPConfig.load(LINKEDIN_MCP_CONFIG_PATH)
    assert os.path.isabs(config.cwd)
    assert config.cwd.endswith("StagePilot-Automation")


def test_env_overrides_command_and_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKEDIN_MCP_COMMAND", "ci-python")
    monkeypatch.setenv("LINKEDIN_MCP_CWD", "ci-server-dir")

    config = LinkedInMCPConfig.load(LINKEDIN_MCP_CONFIG_PATH)

    assert config.command == "ci-python"
    assert os.path.isabs(config.cwd)
    assert os.path.basename(config.cwd) == "ci-server-dir"


def test_bare_executable_is_not_made_repository_relative() -> None:
    assert _resolve_command("python") == "python"
    assert _resolve_command("uvx") == "uvx"


def test_relative_command_resolves_against_repo_root() -> None:
    local = "venv/bin/ci-python"
    resolved = _resolve_command(local)
    assert os.path.isabs(resolved)
    assert Path(resolved).name == "ci-python"
