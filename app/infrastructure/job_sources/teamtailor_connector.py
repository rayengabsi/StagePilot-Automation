from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime
from app.shared.time import utc_now

_TEAMTAILOR_API = "https://api.teamtailor.com/v1/jobs"
_PAGE_SIZE = 100


class TeamtailorConnector(BaseJobSourceConnector):
    """Fetch public Teamtailor job boards via the Teamtailor v1 API."""

    source_type: ClassVar[JobSourceType] = JobSourceType.TEAMTAILOR
    provider_name: ClassVar[str] = "teamtailor"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate the Teamtailor source configuration."""
        errors = super().validate(source)
        if not source.config.get("api_key"):
            errors.append("teamtailor api_key is required in config")
        return errors

    def _build_headers(self, source: JobSourceConfig) -> dict[str, str]:
        """Return Teamtailor authorization headers when an API key is set."""
        api_key = source.config.get("api_key")
        if not api_key:
            return {}
        return {"Authorization": f"Token api_key={api_key}"}

    def _health_url(self, source: JobSourceConfig) -> str:  # noqa: ARG002
        """Health checks hit the Teamtailor jobs endpoint."""
        return _TEAMTAILOR_API

    def _initial_cursor(self, source: JobSourceConfig) -> int:  # noqa: ARG002
        """Teamtailor pagination starts at page 1."""
        return 1

    def _fetch_page(self, source: JobSourceConfig, cursor: int) -> PageResult:
        """Fetch one page of Teamtailor jobs with related entities."""
        params = {
            "page[size]": _PAGE_SIZE,
            "page[number]": cursor,
            "include": "department,location",
        }
        data = self._http.get_json(
            _TEAMTAILOR_API,
            params=params,
            headers=self._build_headers(source),
        )
        items = data.get("data") or []
        included = data.get("included") or []
        meta = data.get("meta") or {}
        pagination = meta.get("pagination") or {}
        current_page = int(pagination.get("current-page", cursor))
        last_page = int(pagination.get("last-page", 0) or current_page)
        next_cursor = current_page + 1 if current_page < last_page else None
        return PageResult(
            items=[_EnrichedJob(raw, included) for raw in items],
            next_cursor=next_cursor,
        )

    def normalize(
        self, raw: dict[str, Any], source: JobSourceConfig
    ) -> DiscoveredJob | None:
        """Convert a Teamtailor job payload into a discovered job."""
        if not isinstance(raw, _EnrichedJob):
            raw = _EnrichedJob(raw, [])
        title = clean_text(raw.attributes.get("title"))
        url = clean_text(raw.attributes.get("url"))
        if not title or not url:
            return None

        location_name = raw.location_name()
        description = clean_text(
            raw.attributes.get("body")
            or raw.attributes.get("description")
            or raw.attributes.get("headline")
        )

        return DiscoveredJob(
            external_id=clean_text(raw.data.get("id")),
            url=url,
            title=title,
            company=source.config.get("company") or self._company_slug(source),
            location=location_name,
            description=description,
            department=raw.department_name(),
            employment_type=clean_text(raw.attributes.get("employment-type")),
            remote_status="remote" if bool(raw.attributes.get("remote")) else None,
            raw_payload=raw.data,
            discovered_at=utc_now(),
            posted_at=parse_datetime(raw.attributes.get("created-at")),
        )

    def _company_slug(self, source: JobSourceConfig) -> str | None:
        """Infer a company name from the base_url host."""
        host = urlparse(source.base_url).hostname or ""
        return host.split(".")[0] or None


class _EnrichedJob:
    """Wrapper that resolves Teamtailor relationship IDs via the included array."""

    __slots__ = ("_included", "data")

    def __init__(self, data: dict[str, Any], included: list[dict[str, Any]]) -> None:
        """Store the job data and related entities."""
        self.data = data
        self._included = included

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the job attributes map."""
        attrs = self.data.get("attributes") or {}
        return attrs if isinstance(attrs, dict) else {}

    def _related(self, relationship: str) -> dict[str, Any] | None:
        """Return the included entity for a named relationship."""
        rel = self.data.get("relationships") or {}
        entry = rel.get(relationship) or {}
        ref = entry.get("data")
        if not isinstance(ref, dict) or not ref.get("id"):
            return None
        for entity in self._included:
            if not isinstance(entity, dict):
                continue
            if entity.get("id") == ref["id"] and entity.get("type") == ref.get("type"):
                return entity
        return None

    def department_name(self) -> str | None:
        """Resolve the department name from the included entities."""
        entity = self._related("department")
        if not entity:
            return None
        attrs = entity.get("attributes") or {}
        return clean_text(attrs.get("name"))

    def location_name(self) -> str | None:
        """Resolve the location name from the included entities."""
        entity = self._related("location")
        if not entity:
            return None
        attrs = entity.get("attributes") or {}
        city = clean_text(attrs.get("city"))
        country = clean_text(attrs.get("country"))
        if city and country:
            return f"{city}, {country}"
        return city or country
