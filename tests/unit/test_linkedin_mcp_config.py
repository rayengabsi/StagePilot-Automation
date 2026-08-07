"""Unit tests for cross-platform LinkedIn MCP configuration.

These verify that the server location comes only from the TOML or environment
variables (never a machine-specific absolute path), and that bare executables
resolve through PATH on every OS.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.config.linkedin_mcp_config import (
    LINKEDIN_MCP_CONFIG_PATH,
    LinkedInMCPConfig,
    _effective_env,
    _resolve_command,
)


def _load(env: dict[str, str] | None = None, env_file: Path | None = None) -> LinkedInMCPConfig:
    return LinkedInMCPConfig.load(LINKEDIN_MCP_CONFIG_PATH, env=env, env_file=env_file)


def test_default_command_is_cross_platform_bare_executable(tmp_path: Path) -> None:
    config = _load(env={}, env_file=tmp_path / "empty.env")
    assert config.command == "python"
    assert not os.path.isabs(config.command)


def test_default_cwd_is_repository_relative(tmp_path: Path) -> None:
    config = _load(env={}, env_file=tmp_path / "empty.env")
    assert os.path.isabs(config.cwd)
    assert config.cwd.endswith("StagePilot-Automation")


def test_env_overrides_command_and_cwd(tmp_path: Path) -> None:
    config = _load(
        env={"LINKEDIN_MCP_COMMAND": "ci-python", "LINKEDIN_MCP_CWD": "ci-server-dir"},
        env_file=tmp_path / "empty.env",
    )

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


def test_env_file_overrides_populate_effective_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "STAGEPILOT_IGNORED=1\n"
        "# comment\n"
        "LINKEDIN_MCP_COMMAND=/opt/server/bin/python\n"
        "\n"
        "LINKEDIN_MCP_CWD=/opt/server\n",
        encoding="utf-8",
    )

    env = _effective_env(env={}, env_file=env_file)

    assert env["LINKEDIN_MCP_COMMAND"] == "/opt/server/bin/python"
    assert env["LINKEDIN_MCP_CWD"] == "/opt/server"


def test_env_file_does_not_override_real_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LINKEDIN_MCP_COMMAND=/ignored\n", encoding="utf-8")

    env = _effective_env(
        env={"LINKEDIN_MCP_COMMAND": "from-real-env"},
        env_file=env_file,
    )

    assert env["LINKEDIN_MCP_COMMAND"] == "from-real-env"


def test_missing_env_file_is_ignored(tmp_path: Path) -> None:
    env = _effective_env(env={"KEEP": "1"}, env_file=tmp_path / "does-not-exist.env")
    assert env == {"KEEP": "1"}
