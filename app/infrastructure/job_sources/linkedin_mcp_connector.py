"""LinkedIn MCP job source connector.

Retrieves jobs from the real LinkedIn MCP server over stdio and adapts them
to the standard ``DiscoveredJob`` shape consumed by the existing discovery
pipeline.

Lifecycle (all automatic, no manual server startup):

    Start MCP  ->  Connect over stdio  ->  Call ``search_jobs``
      ->  Call ``get_job_details`` per job  ->  Normalize  ->  Return jobs
      ->  Close the MCP connection (the child process exits)

The connector's only responsibility is search → normalize → return
``DiscoveredJob``. Matching, filtering and persistence live elsewhere and are
unchanged. If the server reports an expired LinkedIn session, the connector
raises ``LinkedInSessionExpiredError`` so the caller can print re-login steps.
"""

from __future__ import annotations

import shlex
import time
from collections.abc import Callable
from functools import partial
from typing import Any, ClassVar, TypeVar

from app.config.linkedin_mcp_config import LinkedInMCPConfig, get_linkedin_mcp_config
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig, ProviderHealth
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import LinkedInSessionExpiredError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.linkedin_mcp.client import LinkedInMCPClient, LinkedInMCPError
from app.infrastructure.linkedin_mcp.job_parser import ParsedLinkedInJob, parse_linkedin_job_posting
from app.shared.time import utc_now

T = TypeVar("T")

_DEFAULT_SEARCH_TOOL = "search_jobs"
_DEFAULT_DETAIL_TOOL = "get_job_details"

_SEARCH_ARG_KEYS = (
    "keywords",
    "location",
    "experience_level",
    "work_type",
    "job_type",
    "date_posted",
    "sort_by",
)


class LinkedInMCPConnector(BaseJobSourceConnector):
    """Fetch jobs from the real LinkedIn MCP server over stdio."""

    source_type: ClassVar[JobSourceType] = JobSourceType.LINKEDIN_MCP
    provider_name: ClassVar[str] = "linkedin_mcp"

    def __init__(
        self,
        settings: object,
        config: object | None = None,
        http_client: object | None = None,
        rate_limiter: object | None = None,
        mcp_config: LinkedInMCPConfig | None = None,
    ) -> None:
        super().__init__(settings, config, http_client, rate_limiter)  # type: ignore[arg-type]
        self._server = mcp_config or get_linkedin_mcp_config()
        self._retry_attempts = getattr(self._server, "retry_attempts", 3)
        self._retry_delay_seconds = getattr(self._server, "retry_delay_seconds", 2.0)
        self._retry_backoff = getattr(self._server, "retry_backoff", 2.0)

    def fetch(self, source: JobSourceConfig) -> list[DiscoveredJob]:
        """Start the MCP server, search, fetch details, and normalize jobs."""
        client = self._build_client(source)
        search_result = self._with_retry(
            lambda: self._search(client, source)
        )
        job_ids = _extract_job_ids(search_result)

        if not job_ids:
            return []

        limit = self._server.max_jobs
        selected = job_ids[:limit]
        detail_tool = self._detail_tool(source)
        return self._fetch_details(client, selected, detail_tool)

    def _fetch_details(
        self, client: LinkedInMCPClient, selected: list[str], detail_tool: str
    ) -> list[DiscoveredJob]:
        """Fetch job details with retries and per-job recovery.

        Transient failures are retried; otherwise details are fetched one job
        at a time so a single bad listing never sinks the whole fetch.
        """
        detail_calls = [(detail_tool, {"job_id": job_id}) for job_id in selected]
        try:
            responses = self._with_retry(lambda: client.call_many(detail_calls))
        except LinkedInSessionExpiredError:
            raise
        except LinkedInMCPError:
            # call_many is all-or-nothing: after it exhausts its retries we fall
            # back to fetching each job individually so partial results survive.
            return self._recover_details(client, selected, detail_tool)

        jobs: list[DiscoveredJob] = []
        for response, job_id in zip(responses, selected, strict=True):
            parsed = _job_from_response(response, job_id)
            if parsed is not None:
                jobs.append(_to_discovered_job(parsed))
        return jobs

    def _recover_details(
        self, client: LinkedInMCPClient, selected: list[str], detail_tool: str
    ) -> list[DiscoveredJob]:
        """Fetch details per-job, skipping (not failing on) any that error."""
        jobs: list[DiscoveredJob] = []
        for job_id in selected:
            try:
                response = self._with_retry(
                    partial(client.call_tool, detail_tool, {"job_id": job_id}),
                )
            except (LinkedInMCPError, LinkedInSessionExpiredError):
                continue
            parsed = _job_from_response(response, job_id)
            if parsed is not None:
                jobs.append(_to_discovered_job(parsed))
        return jobs

    def _with_retry(self, operation: Callable[[], T]) -> T:
        """Run ``operation``, retrying transient errors with exponential backoff.

        An expired-session error is never retried. Returns the operation result
        or re-raises a ``LinkedInMCPError`` once attempts are exhausted.
        """
        delay = self._retry_delay_seconds
        for attempt in range(self._retry_attempts + 1):
            try:
                return operation()
            except LinkedInSessionExpiredError:
                raise
            except LinkedInMCPError:
                if attempt >= self._retry_attempts:
                    raise
                time.sleep(delay)
                delay *= self._retry_backoff
        raise LinkedInMCPError("LinkedIn MCP retry policy exhausted")

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that an MCP server command is available for the source."""
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
        except LinkedInSessionExpiredError:
            raise
        except Exception as exc:
            latency = round((time.monotonic() - started) * 1000, 2)
            return ProviderHealth(
                provider=self.provider_name,
                status="unhealthy",
                latency_ms=latency,
                message=str(exc),
                checked_at=utc_now(),
            )

    def _search(self, client: LinkedInMCPClient, source: JobSourceConfig) -> dict[str, Any]:
        """Run the search tool and return its dict payload."""
        try:
            result = client.call_tool(
                self._search_tool(source), self._build_search_arguments(source)
            )
        except LinkedInMCPError as exc:
            self._raise_if_session_expired(exc)
            raise
        return result if isinstance(result, dict) else {}

    def normalize(
        self,
        raw: dict[str, Any],
        source: JobSourceConfig,  # noqa: ARG002
    ) -> DiscoveredJob | None:
        """Convert a parsed LinkedIn payload or structured dict into a job."""
        if isinstance(raw, dict) and {"job_id", "title"}.issubset(raw):
            job_id = str(raw.get("job_id") or "")
            if not job_id:
                return None
            url = str(raw.get("url") or f"https://www.linkedin.com/jobs/view/{job_id}/")
            return DiscoveredJob(
                external_id=str(raw.get("job_id")),
                url=url,
                title=str(raw.get("title") or f"LinkedIn Job {job_id}"),
                company=_opt_str(raw.get("company")),
                location=_opt_str(raw.get("location")),
                description=_opt_str(raw.get("description")),
                requirements=_opt_str(raw.get("requirements")),
                remote_status=_opt_str(raw.get("work_mode")),
                raw_payload=dict(raw),
                discovered_at=utc_now(),
            )
        return _from_legacy_dict(raw)

    def _fetch_page(self, _source: JobSourceConfig, _cursor: Any) -> PageResult:  # noqa: ANN401
        """Unused: LinkedIn searches are single-shot and handled in ``fetch``."""
        return PageResult(items=[], next_cursor=None)

    def _build_client(self, source: JobSourceConfig) -> LinkedInMCPClient:
        """Build an MCP client from the source config and server defaults."""
        command = self._server_command(source)
        if not command:
            raise LinkedInMCPError("linkedin_mcp source requires a server command")
        config = source.config
        env = config.get("server_env")
        if env is not None and not isinstance(env, dict):
            raise LinkedInMCPError("server_env must be a JSON object")
        return LinkedInMCPClient(
            command=command,
            args=_server_args(config, self._server),
            env={str(k): str(v) for k, v in env.items()} if env else None,
            cwd=str(config.get("server_cwd") or self._server.cwd),
            timeout_seconds=_as_float(
                config.get("timeout_seconds"), default=self._server.timeout_seconds
            ),
        )

    def _server_command(self, source: JobSourceConfig) -> str | None:
        configured = source.config.get("server_command")
        if configured:
            return str(configured)
        if source.base_url:
            return str(source.base_url)
        return self._server.command

    def _search_tool(self, source: JobSourceConfig) -> str:
        return str(
            source.config.get("search_tool")
            or source.config.get("tool_name")
            or _DEFAULT_SEARCH_TOOL
        )

    def _detail_tool(self, source: JobSourceConfig) -> str:
        return str(source.config.get("detail_tool") or _DEFAULT_DETAIL_TOOL)

    def _build_search_arguments(self, source: JobSourceConfig) -> dict[str, Any]:
        """Merge source search filters over the server defaults."""
        config = source.config
        arguments: dict[str, Any] = {
            key: str(config[key]) for key in _SEARCH_ARG_KEYS if config.get(key)
        }
        if not arguments.get("experience_level") and self._server.experience_level:
            arguments["experience_level"] = self._server.experience_level
        if not arguments.get("job_type") and self._server.job_type:
            arguments["job_type"] = self._server.job_type
        arguments["max_pages"] = _as_int(config.get("max_pages"), default=self._server.max_pages)
        if self._server.date_posted and not config.get("date_posted"):
            arguments["date_posted"] = self._server.date_posted
        if self._server.sort_by and not config.get("sort_by"):
            arguments["sort_by"] = self._server.sort_by
        return arguments

    def _raise_if_session_expired(self, exc: BaseException) -> None:
        """Raise LinkedInSessionExpiredError when the error mentions an expired session."""
        text = str(exc).lower()
        if any(marker in text for marker in self._server.expired_markers):
            raise LinkedInSessionExpiredError(str(exc)) from exc


def _job_from_response(response: object, job_id: str) -> ParsedLinkedInJob | None:
    """Parse a get_job_details response into a ParsedLinkedInJob."""
    if not isinstance(response, dict):
        return None
    sections = response.get("sections")
    if not isinstance(sections, dict):
        return None
    text = sections.get("job_posting")
    if not text or not isinstance(text, str) or not text.strip():
        return None
    return parse_linkedin_job_posting(text, job_id)


def _to_discovered_job(parsed: ParsedLinkedInJob) -> DiscoveredJob:
    return DiscoveredJob(
        external_id=parsed.job_id,
        url=parsed.url,
        title=parsed.title or f"LinkedIn Job {parsed.job_id}",
        company=parsed.company,
        location=parsed.location,
        description=parsed.description,
        requirements=parsed.requirements,
        employment_type=parsed.employment_type,
        remote_status=parsed.work_mode,
        posted_at=parsed.posted_at,
        raw_payload=parsed.to_payload(),
        discovered_at=utc_now(),
    )


def _extract_job_ids(result: dict[str, Any]) -> list[str]:
    """Extract the numeric job ids from a search_jobs result."""
    raw = result.get("job_ids")
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _server_args(config: dict[str, Any], server: LinkedInMCPConfig) -> list[str]:
    """Resolve server args from a source override or the configured defaults."""
    configured = config.get("server_args")
    if isinstance(configured, list):
        return [str(item) for item in configured]
    if isinstance(configured, str) and configured.strip():
        return shlex.split(configured)
    return server.base_arguments()


def _from_legacy_dict(raw: dict[str, Any]) -> DiscoveredJob:
    """Normalize a structured LinkedIn job dict (legacy payload shapes)."""

    def first(*keys: str) -> str | None:
        for key in keys:
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
        return None

    title = first("title", "job_title", "position", "name")
    url = first("url", "external_url", "apply_url", "link")
    if not title or not url:
        return None
    return DiscoveredJob(
        external_id=first("external_id", "job_id", "remote_id", "id") or url,
        url=url,
        title=title,
        company=first("company", "company_name", "organization"),
        location=first("location", "city", "formatted_location") or "Remote",
        description=first("description", "job_description", "summary"),
        requirements=first("requirements", "skills"),
        employment_type=first("employment_type", "employmentType", "job_type", "work_type"),
        remote_status=first("remote_status", "remoteStatus", "workplace_type", "work_mode"),
        raw_payload=dict(raw),
        discovered_at=utc_now(),
    )


def _opt_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _as_int(value: object, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
