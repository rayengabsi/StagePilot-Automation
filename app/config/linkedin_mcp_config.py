from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LINKEDIN_MCP_CONFIG_PATH = Path(__file__).parent / "linkedin_mcp.toml"
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Environment variables that override the TOML values so the LinkedIn MCP
# server location is never hard-coded to one developer's machine. Setting these
# keeps every OS working without editing code.
_LINKEDIN_MCP_ENV = {
    "command": "LINKEDIN_MCP_COMMAND",
    "cwd": "LINKEDIN_MCP_CWD",
    "module": "LINKEDIN_MCP_MODULE",
    "log_level": "LINKEDIN_MCP_LOG_LEVEL",
    "user_data_dir": "LINKEDIN_MCP_USER_DATA_DIR",
}


@dataclass(frozen=True, slots=True)
class LinkedInMCPConfig:
    command: str
    cwd: str
    module: str
    transport: str
    timeout_seconds: float
    tool_timeout_seconds: float
    log_level: str
    max_jobs: int
    max_pages: int
    date_posted: str
    sort_by: str
    job_type: str
    experience_level: str
    expired_markers: tuple[str, ...]
    user_data_dir: str
    login_headed: bool
    login_timeout_seconds: float
    status_timeout_seconds: float
    status_probe_timeout_seconds: float
    startup_timeout_seconds: float
    shutdown_timeout_seconds: float
    ready_poll_seconds: float
    state_file: Path
    max_matching_skills: int
    max_missing_skills: int
    retry_attempts: int
    retry_delay_seconds: float
    retry_backoff: float

    @classmethod
    def load(cls, path: Path = LINKEDIN_MCP_CONFIG_PATH) -> LinkedInMCPConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        gateway = raw["gateway"]
        auth = gateway.get("auth", {})
        retry = gateway.get("retry", {})
        notify = raw.get("notify", {})
        lifecycle = gateway.get("lifecycle", {})
        return cls(
            command=_resolve_command(_env_or(gateway["command"], "command")),
            cwd=_resolve(_env_or(gateway.get("cwd", "."), "cwd")),
            module=str(_env_or(gateway.get("module", "linkedin_mcp_server"), "module")),
            transport=str(gateway.get("transport", "stdio")),
            timeout_seconds=float(gateway.get("timeout_seconds", 90.0)),
            tool_timeout_seconds=float(gateway.get("tool_timeout_seconds", 180.0)),
            log_level=str(_env_or(gateway.get("log_level", "WARNING"), "log_level")),
            max_jobs=int(gateway.get("max_jobs", 8)),
            max_pages=int(gateway.get("max_pages", 3)),
            date_posted=str(gateway.get("date_posted", "")),
            sort_by=str(gateway.get("sort_by", "")),
            job_type=str(gateway.get("job_type", "")),
            experience_level=str(gateway.get("experience_level", "")),
            expired_markers=tuple(str(m).lower() for m in auth.get("expired_markers", [])),
            user_data_dir=str(_env_or(auth.get("user_data_dir", ""), "user_data_dir")),
            login_headed=bool(auth.get("login_headed", True)),
            login_timeout_seconds=float(auth.get("login_timeout_seconds", 3600.0)),
            status_timeout_seconds=float(auth.get("status_timeout_seconds", 300.0)),
            status_probe_timeout_seconds=float(auth.get("status_probe_timeout_seconds", 20.0)),
            startup_timeout_seconds=float(lifecycle.get("startup_timeout_seconds", 90.0)),
            shutdown_timeout_seconds=float(lifecycle.get("shutdown_timeout_seconds", 15.0)),
            ready_poll_seconds=float(lifecycle.get("ready_poll_seconds", 2.0)),
            state_file=Path(_resolve(notify.get("state_file", "data/linkedin/notified.json"))),
            max_matching_skills=int(notify.get("max_matching_skills", 5)),
            max_missing_skills=int(notify.get("max_missing_skills", 5)),
            retry_attempts=int(retry.get("retry_attempts", 3)),
            retry_delay_seconds=float(retry.get("retry_delay_seconds", 2.0)),
            retry_backoff=float(retry.get("retry_backoff", 2.0)),
        )

    def base_arguments(self) -> list[str]:
        """Command-line arguments that launch the server over stdio."""
        args = ["-m", self.module, "--transport", self.transport]
        if self.log_level:
            args.append("--log-level")
            args.append(self.log_level)
        return args


@lru_cache(maxsize=1)
def get_linkedin_mcp_config(path: Path = LINKEDIN_MCP_CONFIG_PATH) -> LinkedInMCPConfig:
    """Return the cached LinkedIn MCP production configuration."""
    return LinkedInMCPConfig.load(path)


def _resolve(value: str) -> str:
    """Expand a config path relative to the repository root or home dir."""
    text = os.path.expanduser(value.strip())
    path = Path(text)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return str(path)


def _resolve_command(value: str) -> str:
    """Resolve a server command without making bare executables repo-relative.

    An absolute path (or one with a separator) is resolved against the
    repository root, but a plain executable name such as ``python`` or ``uvx``
    is left untouched so it is found on ``PATH`` on every OS.
    """
    text = os.path.expanduser(value.strip())
    if not text:
        return text
    if "/" not in text and "\\" not in text and not text.startswith((".", "~")):
        return text
    path = Path(text)
    if path.is_absolute():
        return str(path)
    return str(_REPO_ROOT / path)


def _env_or(toml_value: str, key: str) -> str:
    """Return the environment override for ``key`` when set, else ``toml_value``."""
    env_name = _LINKEDIN_MCP_ENV[key]
    value = os.environ.get(env_name)
    return value if value is not None else str(toml_value)
