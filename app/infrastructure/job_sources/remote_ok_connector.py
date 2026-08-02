from __future__ import annotations

from typing import Any, ClassVar

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime, strip_html
from app.shared.time import utc_now

_REMOTE_OK_API = "https://remoteok.com/api"


class RemoteOkConnector(BaseJobSourceConnector):
    """Fetch remote jobs from the RemoteOK public API."""

    source_type: ClassVar[JobSourceType] = JobSourceType.REMOTE_OK
    provider_name: ClassVar[str] = "remote_ok"

    def _build_headers(self, source: JobSourceConfig) -> dict[str, str]:  # noqa: ARG002
        """Return the JSON accept header expected by RemoteOK."""
        return {"Accept": "application/json"}

    def _health_url(self, source: JobSourceConfig) -> str:  # noqa: ARG002
        """Health checks hit the RemoteOK API endpoint."""
        return _REMOTE_OK_API

    def _fetch_page(self, source: JobSourceConfig, cursor: Any) -> PageResult:  # noqa: ANN401, ARG002
        """Fetch the RemoteOK job feed (single page, no pagination)."""
        data = self._http.get_json(
            _REMOTE_OK_API,
            headers=self._build_headers(source),
        )
        if not isinstance(data, list):
            return PageResult(items=[], next_cursor=None)
        jobs = [item for item in data if isinstance(item, dict) and item.get("id") is not None]
        return PageResult(items=jobs, next_cursor=None)

    def normalize(
        self, raw: dict[str, Any], source: JobSourceConfig  # noqa: ARG002
    ) -> DiscoveredJob | None:
        """Convert a RemoteOK job payload into a discovered job."""
        title = clean_text(raw.get("position"))
        url = clean_text(raw.get("url") or raw.get("apply_url"))
        if not title or not url:
            return None

        tags = raw.get("tags")
        requirements = (
            ", ".join(str(tag) for tag in tags) if isinstance(tags, list) and tags else None
        )

        return DiscoveredJob(
            external_id=str(raw.get("id")),
            url=url,
            title=title,
            company=clean_text(raw.get("company")),
            location=clean_text(raw.get("location")) or "Remote",
            description=strip_html(raw.get("description")),
            department=None,
            employment_type=None,
            remote_status="remote",
            requirements=requirements,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=parse_datetime(raw.get("date")),
        )
