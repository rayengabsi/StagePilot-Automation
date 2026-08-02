from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime, strip_html
from app.shared.time import utc_now

_ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{board}"


class AshbyConnector(BaseJobSourceConnector):
    """Fetch public Ashby job boards via the Ashby posting API."""

    source_type: ClassVar[JobSourceType] = JobSourceType.ASHBY
    provider_name: ClassVar[str] = "ashby"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that an Ashby board identifier is available."""
        errors = super().validate(source)
        if not self._board_identifier(source):
            errors.append("ashby board identifier is required (config.board or base_url path)")
        return errors

    def _board_identifier(self, source: JobSourceConfig) -> str | None:
        """Determine the Ashby board identifier from config or base_url."""
        board = source.config.get("board")
        if board:
            return str(board)
        path = urlparse(source.base_url).path.strip("/")
        if path:
            return path.split("/")[-1]
        return None

    def _initial_cursor(self, source: JobSourceConfig) -> str | None:  # noqa: ARG002
        """Ashby pagination starts with no cursor."""
        return None

    def _fetch_page(self, source: JobSourceConfig, cursor: str | None) -> PageResult:
        """Fetch one page of Ashby jobs."""
        board = self._board_identifier(source)
        if board is None:
            raise SourceConfigError("ashby board identifier is required")
        url = _ASHBY_API.format(board=board)
        body: dict[str, Any] = {
            "boardIdentifier": board,
            "includeCompensation": False,
        }
        if cursor:
            body["paginationCursor"] = cursor
        data = self._http.post_json(url, json=body)
        jobs = data.get("jobs") or []
        next_cursor = data.get("nextCursor") if data.get("hasMore") else None
        return PageResult(items=jobs, next_cursor=next_cursor)

    def normalize(
        self, raw: dict[str, Any], source: JobSourceConfig
    ) -> DiscoveredJob | None:
        """Convert an Ashby job payload into a discovered job."""
        title = clean_text(raw.get("title"))
        url = clean_text(raw.get("jobUrl"))
        if not title or not url:
            return None

        description_html = raw.get("descriptionHtml")
        description = clean_text(raw.get("descriptionPlain")) or strip_html(description_html)

        return DiscoveredJob(
            external_id=clean_text(raw.get("id")),
            url=url,
            title=title,
            company=source.config.get("company") or self._board_identifier(source),
            location=clean_text(raw.get("location")),
            description=description,
            department=clean_text(raw.get("department") or raw.get("team")),
            employment_type=clean_text(raw.get("employmentType")),
            remote_status=self._detect_remote(raw),
            requirements=None,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=parse_datetime(raw.get("publishedAt")),
        )

    def _detect_remote(self, raw: dict[str, Any]) -> str | None:
        """Detect remote status from location or employment metadata."""
        location = (raw.get("location") or "").lower()
        if "remote" in location:
            return "remote"
        if "hybrid" in location:
            return "hybrid"
        return None
