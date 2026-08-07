from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LINKEDIN_MCP_CONFIG_PATH = Path(__file__).parent / "linkedin_mcp.toml"
_REPO_ROOT = Path(__file__).resolve().parents[2]


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
            command=_resolve(gateway["command"]),
            cwd=_resolve(gateway.get("cwd", ".")),
            module=str(gateway.get("module", "linkedin_mcp_server")),
            transport=str(gateway.get("transport", "stdio")),
            timeout_seconds=float(gateway.get("timeout_seconds", 90.0)),
            tool_timeout_seconds=float(gateway.get("tool_timeout_seconds", 180.0)),
            log_level=str(gateway.get("log_level", "WARNING")),
            max_jobs=int(gateway.get("max_jobs", 8)),
            max_pages=int(gateway.get("max_pages", 3)),
            date_posted=str(gateway.get("date_posted", "")),
            sort_by=str(gateway.get("sort_by", "")),
            job_type=str(gateway.get("job_type", "")),
            experience_level=str(gateway.get("experience_level", "")),
            expired_markers=tuple(str(m).lower() for m in auth.get("expired_markers", [])),
            user_data_dir=str(auth.get("user_data_dir", "")),
            login_headed=bool(auth.get("login_headed", True)),
            login_timeout_seconds=float(auth.get("login_timeout_seconds", 3600.0)),
            status_timeout_seconds=float(auth.get("status_timeout_seconds", 300.0)),
            status_probe_timeout_seconds=float(
                auth.get("status_probe_timeout_seconds", 20.0)
            ),
            startup_timeout_seconds=float(
                lifecycle.get("startup_timeout_seconds", 90.0)
            ),
            shutdown_timeout_seconds=float(
                lifecycle.get("shutdown_timeout_seconds", 15.0)
            ),
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
