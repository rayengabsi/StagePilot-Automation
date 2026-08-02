from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime
from app.shared.time import utc_now

_GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseConnector(BaseJobSourceConnector):
    """Fetch public Greenhouse job board postings."""

    source_type: ClassVar[JobSourceType] = JobSourceType.GREENHOUSE
    provider_name: ClassVar[str] = "greenhouse"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that a Greenhouse board token is available."""
        errors = super().validate(source)
        if not self._board_token(source):
            errors.append("greenhouse board token is required (config.token or base_url path)")
        return errors

    def _board_token(self, source: JobSourceConfig) -> str | None:
        """Determine the Greenhouse board token from config or base_url."""
        token = source.config.get("token")
        if token:
            return str(token)
        path = urlparse(source.base_url).path.rstrip("/")
        if path:
            return path.rsplit("/", 1)[-1]
        return None

    def _initial_cursor(self, source: JobSourceConfig) -> int:  # noqa: ARG002
        """Greenhouse pagination starts at page 1."""
        return 1

    def _fetch_page(self, source: JobSourceConfig, cursor: int) -> PageResult:
        """Fetch one page of Greenhouse jobs."""
        token = self._board_token(source)
        if token is None:
            raise SourceConfigError("greenhouse board token is required")
        url = _GREENHOUSE_API.format(token=token)
        data = self._http.get_json(url, params={"content": "true", "page": cursor})
        jobs = data.get("jobs") or []
        meta = data.get("meta") or {}
        page = int(meta.get("page", cursor))
        total = int(meta.get("total", 0) or 0)
        per_page = int(meta.get("per_page", 0) or len(jobs) or 1)
        next_cursor = page + 1 if jobs and page * per_page < total else None
        return PageResult(items=jobs, next_cursor=next_cursor)

    def normalize(
        self, raw: dict[str, Any], source: JobSourceConfig
    ) -> DiscoveredJob | None:
        """Convert a Greenhouse job payload into a discovered job."""
        title = clean_text(raw.get("title"))
        url = clean_text(raw.get("absolute_url"))
        if not title or not url:
            return None

        location = self._location_name(raw.get("location"))
        departments = raw.get("departments") or []
        department = clean_text(departments[0].get("name")) if departments else None
        employment_raw = raw.get("employment_type") or {}
        employment_type = (
            clean_text(employment_raw.get("name"))
            if isinstance(employment_raw, dict)
            else clean_text(employment_raw)
        )
        remote_status = "remote" if bool(raw.get("remote")) else None

        return DiscoveredJob(
            external_id=str(raw["id"]) if raw.get("id") is not None else None,
            url=url,
            title=title,
            company=source.config.get("company") or self._board_token(source),
            location=location,
            description=clean_text(raw.get("content")),
            department=department,
            employment_type=employment_type,
            remote_status=remote_status,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=parse_datetime(raw.get("updated_at")),
        )

    def _location_name(self, location: Any) -> str | None:  # noqa: ANN401
        """Extract a location name from Greenhouse's flexible location field."""
        if isinstance(location, dict):
            return clean_text(location.get("name"))
        return clean_text(location) if location else None
