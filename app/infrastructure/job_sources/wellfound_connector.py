from __future__ import annotations

from typing import Any, ClassVar

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime, strip_html
from app.shared.time import utc_now

_WELLFOUND_API = "https://api.angel.co/v1/jobs"
_PAGE_SIZE = 50


class WellfoundConnector(BaseJobSourceConnector):
    """Fetch startup jobs from the Wellfound (AngelList) public API."""

    source_type: ClassVar[JobSourceType] = JobSourceType.WELLFOUND
    provider_name: ClassVar[str] = "wellfound"

    def _build_headers(self, source: JobSourceConfig) -> dict[str, str]:  # noqa: ARG002
        """Return the JSON accept header expected by Wellfound."""
        return {"Accept": "application/json"}

    def _health_url(self, source: JobSourceConfig) -> str:  # noqa: ARG002
        """Health checks hit the Wellfound jobs endpoint."""
        return _WELLFOUND_API

    def _params(self, source: JobSourceConfig) -> dict[str, Any]:
        """Build the base query parameters for Wellfound requests."""
        params: dict[str, Any] = {"limit": _PAGE_SIZE, "offset": 0}
        token = source.config.get("token")
        if token:
            params["access_token"] = str(token)
        return params

    def _initial_cursor(self, source: JobSourceConfig) -> int:  # noqa: ARG002
        """Wellfound pagination starts at offset 0."""
        return 0

    def _fetch_page(self, source: JobSourceConfig, cursor: int) -> PageResult:
        """Fetch one page of Wellfound jobs."""
        params = self._params(source)
        params["offset"] = cursor
        data = self._http.get_json(
            _WELLFOUND_API,
            params=params,
            headers=self._build_headers(source),
        )
        jobs = data.get("jobs") if isinstance(data, dict) else []
        if not isinstance(jobs, list):
            jobs = []
        total = int(data.get("total", 0) or 0) if isinstance(data, dict) else 0
        last_page = int(data.get("last_page", 0) or 0) if isinstance(data, dict) else 0
        reached_end = len(jobs) < _PAGE_SIZE or (last_page and cursor + _PAGE_SIZE >= total)
        next_cursor = None if reached_end else cursor + _PAGE_SIZE
        return PageResult(items=jobs, next_cursor=next_cursor)

    def normalize(self, raw: dict[str, Any], source: JobSourceConfig) -> DiscoveredJob | None:
        """Convert a Wellfound job payload into a discovered job."""
        title = clean_text(raw.get("title"))
        url = self._job_url(raw)
        if not title or not url:
            return None

        company_raw = raw.get("company") or {}
        company = (
            clean_text(company_raw.get("name"))
            if isinstance(company_raw, dict)
            else clean_text(company_raw)
        )
        location_raw = raw.get("location") or {}
        location = (
            clean_text(location_raw.get("display_name"))
            if isinstance(location_raw, dict)
            else clean_text(location_raw)
        )

        return DiscoveredJob(
            external_id=str(raw.get("id")) if raw.get("id") is not None else None,
            url=url,
            title=title,
            company=company or source.config.get("company"),
            location=location,
            description=strip_html(raw.get("description")),
            department=None,
            employment_type=None,
            remote_status=self._detect_remote(raw, location),
            requirements=None,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=parse_datetime(raw.get("created_at")),
        )

    def _job_url(self, raw: dict[str, Any]) -> str | None:
        """Extract the best available job URL from a Wellfound payload."""
        urls = raw.get("urls")
        if isinstance(urls, dict):
            apply_url = clean_text(urls.get("apply_url"))
            if apply_url:
                return apply_url
            api_url = clean_text(urls.get("job_api_url"))
            if api_url:
                return api_url
        return clean_text(raw.get("apply_url"))

    def _detect_remote(self, raw: dict[str, Any], location: str | None) -> str | None:
        """Detect remote status from the payload or location."""
        if raw.get("remote") is True:
            return "remote"
        if location and "remote" in location.lower():
            return "remote"
        return None
