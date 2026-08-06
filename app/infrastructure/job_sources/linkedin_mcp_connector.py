"""LinkedIn MCP job source connector.

Retrieves jobs from a LinkedIn MCP server and adapts them to the standard
``DiscoveredJob`` shape consumed by the existing discovery pipeline. The
connector plugs into ``BaseJobSourceConnector`` like every other provider,
so no matching, filtering, or persistence code needs to change.
"""

from __future__ import annotations

import shlex
import time
from typing import Any, ClassVar

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig, ProviderHealth
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime, strip_html
from app.infrastructure.linkedin_mcp.client import LinkedInMCPClient
from app.shared.time import utc_now

_DEFAULT_TOOL_NAME = "search_jobs"


class LinkedInMCPConnector(BaseJobSourceConnector):
    """Fetch jobs from a LinkedIn MCP server over stdio.

    The MCP server connection lives in the source configuration::

        server_command  - executable that starts the server (falls back to base_url)
        server_args     - extra args for the server process (list or string)
        server_env      - environment overrides for the server process
        server_cwd      - working directory for the server process
        tool_name       - tool to call (default ``search_jobs``)
        keywords        - search keywords forwarded to the tool
        location        - location filter forwarded to the tool
        job_type        - employment type filter forwarded to the tool
        limit           - maximum number of results per call
        timeout_seconds - per-call timeout
    """

    source_type: ClassVar[JobSourceType] = JobSourceType.LINKEDIN_MCP
    provider_name: ClassVar[str] = "linkedin_mcp"

    def fetch(self, source: JobSourceConfig) -> list[DiscoveredJob]:
        """Fetch jobs from the LinkedIn MCP server in a single search call."""
        self._rate_limiter.wait()
        client = self._build_client(source)
        tool_name = self._tool_name(source)
        result = client.call_tool(tool_name, self._build_arguments(source))
        jobs: list[DiscoveredJob] = []
        for item in _extract_job_items(result):
            job = self.normalize(item, source)
            if job is not None:
                jobs.append(job)
        return jobs

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that the MCP server command is configured."""
        errors: list[str] = []
        if not self._server_command(source):
            errors.append("server_command (or base_url) is required")
        return errors

    def health(self, source: JobSourceConfig) -> ProviderHealth:
        """Connect to the MCP server and list its tools as a health check."""
        started = time.monotonic()
        try:
            client = self._build_client(source)
            tools = client.list_tools()
            latency = round((time.monotonic() - started) * 1000, 2)
            message = f"OK (tools: {', '.join(tools)})" if tools else "OK"
            return ProviderHealth(
                provider=self.provider_name,
                status="healthy",
                latency_ms=latency,
                message=message,
                checked_at=utc_now(),
            )
        except Exception as exc:
            latency = round((time.monotonic() - started) * 1000, 2)
            return ProviderHealth(
                provider=self.provider_name,
                status="unhealthy",
                latency_ms=latency,
                message=str(exc),
                checked_at=utc_now(),
            )

    def normalize(
        self,
        raw: dict[str, Any],
        source: JobSourceConfig,  # noqa: ARG002
    ) -> DiscoveredJob | None:
        """Convert one LinkedIn MCP job payload into a discovered job."""
        title = _first(clean_text, raw, "title", "job_title", "name", "position")
        url = _first(clean_text, raw, "url", "redirect_url", "apply_url", "external_url", "link")
        if not title or not url:
            return None
        external_id = _first(_as_text, raw, "external_id", "job_id", "jobkey", "id", "remote_id")
        return DiscoveredJob(
            external_id=external_id or url,
            url=url,
            title=title,
            company=_first(clean_text, raw, "company", "company_name", "organization"),
            location=(
                _first(clean_text, raw, "location", "formatted_location", "location_name", "city")
                or "Remote"
            ),
            description=_first(
                strip_html,
                raw,
                "description",
                "job_description",
                "summary",
                "formatted_description",
            ),
            department=_first(clean_text, raw, "department"),
            employment_type=_first(
                clean_text,
                raw,
                "employment_type",
                "employmentType",
                "job_type",
                "work_type",
            ),
            remote_status=_first(
                clean_text,
                raw,
                "remote_status",
                "remoteStatus",
                "workplace_type",
                "work_mode",
            ),
            requirements=_first(clean_text, raw, "requirements", "skills"),
            raw_payload=dict(raw),
            discovered_at=utc_now(),
            posted_at=parse_datetime(
                raw.get("posted_at")
                or raw.get("postedAt")
                or raw.get("listed_at")
                or raw.get("first_seen")
            ),
        )

    def _fetch_page(self, _source: JobSourceConfig, _cursor: Any) -> PageResult:  # noqa: ANN401
        """Unused: LinkedIn searches are single-shot and handled in ``fetch``."""
        return PageResult(items=[], next_cursor=None)

    def _build_client(self, source: JobSourceConfig) -> LinkedInMCPClient:
        """Build an MCP client from the source configuration."""
        command = self._server_command(source)
        if not command:
            raise SourceConfigError("linkedin_mcp source requires server_command or base_url")
        config = source.config
        args = _split_args(config.get("server_args"))
        env = config.get("server_env")
        if env is not None and not isinstance(env, dict):
            raise SourceConfigError("server_env must be a JSON object")
        cwd = config.get("server_cwd")
        timeout = _as_float(config.get("timeout_seconds"), default=30.0)
        return LinkedInMCPClient(
            command=command,
            args=args,
            env=env,
            cwd=cwd,
            timeout_seconds=timeout,
        )

    def _tool_name(self, source: JobSourceConfig) -> str:
        """Return the MCP tool used for job search."""
        return str(source.config.get("tool_name") or _DEFAULT_TOOL_NAME)

    @staticmethod
    def _server_command(source: JobSourceConfig) -> str | None:
        """Resolve the MCP server command from config or the source URL."""
        configured = source.config.get("server_command")
        if configured:
            return str(configured)
        base_url = (source.base_url or "").strip()
        return base_url or None

    def _build_arguments(self, source: JobSourceConfig) -> dict[str, Any]:
        """Build the search tool arguments from the source configuration."""
        config = source.config
        arguments: dict[str, Any] = {}
        for key in ("keywords", "location", "job_type"):
            value = config.get(key)
            if value:
                arguments[key] = str(value)
        limit = _as_int(config.get("limit"))
        if limit is not None:
            arguments["limit"] = limit
        return arguments


def _extract_job_items(result: object) -> list[dict[str, Any]]:
    """Normalize the raw tool output into a list of job dictionaries."""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        for key in ("jobs", "results", "items", "data", "matches"):
            container = result.get(key)
            if isinstance(container, list):
                return [item for item in container if isinstance(item, dict)]
        if any(key in result for key in ("title", "url", "job_title")):
            return [result]
    return []


def _first(transform: object, raw: dict[str, Any], *keys: str) -> object:
    """Return the first non-blank transformed value among *keys*."""
    for key in keys:
        value = raw.get(key)
        if value is None or value == "":
            continue
        transformed = transform(value)
        if transformed:
            return transformed
    return None


def _as_text(value: object) -> str:
    """Render a raw value as a string."""
    return str(value)


def _as_int(value: object) -> int | None:
    """Parse an integer config value defensively."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: object, default: float) -> float:
    """Parse a float config value defensively."""
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _split_args(value: object) -> list[str]:
    """Split a config value into an argument list."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip():
        return shlex.split(value)
    return []
