from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime, strip_html
from app.shared.time import utc_now

_WTTJ_API = "https://www.welcomekit.co/api/v1/organizations/{slug}/jobs"
_PAGE_SIZE = 100


class WelcomeToTheJungleConnector(BaseJobSourceConnector):
    """Fetch public job postings via the WelcomeKit (WTTJ) API."""

    source_type: ClassVar[JobSourceType] = JobSourceType.WELCOME_TO_THE_JUNGLE
    provider_name: ClassVar[str] = "welcome_to_the_jungle"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that a WelcomeKit organization slug is available."""
        errors = super().validate(source)
        if not self._org_slug(source):
            errors.append(
                "welcome_to_the_jungle organization slug is required "
                "(config.slug or base_url path)"
            )
        return errors

    def _build_headers(self, source: JobSourceConfig) -> dict[str, str]:  # noqa: ARG002
        """Return the JSON accept header expected by WelcomeKit."""
        return {"Accept": "application/json"}

    def _health_url(self, source: JobSourceConfig) -> str:
        """Health checks hit the organization jobs endpoint."""
        slug = self._org_slug(source)
        return _WTTJ_API.format(slug=slug) if slug else source.base_url

    def _org_slug(self, source: JobSourceConfig) -> str | None:
        """Determine the WelcomeKit organization slug."""
        slug = source.config.get("slug")
        if slug:
            return str(slug)
        path = urlparse(source.base_url).path.strip("/")
        if path:
            return path.split("/")[-1]
        return None

    def _initial_cursor(self, source: JobSourceConfig) -> int:  # noqa: ARG002
        """WelcomeKit pagination starts at page 1."""
        return 1

    def _fetch_page(self, source: JobSourceConfig, cursor: int) -> PageResult:
        """Fetch one page of WelcomeKit jobs."""
        slug = self._org_slug(source)
        if slug is None:
            raise SourceConfigError("welcome_to_the_jungle organization slug is required")
        url = _WTTJ_API.format(slug=slug)
        data = self._http.get_json(
            url,
            params={"per_page": _PAGE_SIZE, "page": cursor},
            headers=self._build_headers(source),
        )
        items = data.get("data") if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = []
        next_cursor = cursor + 1 if len(items) >= _PAGE_SIZE else None
        return PageResult(items=items, next_cursor=next_cursor)

    def normalize(
        self, raw: dict[str, Any], source: JobSourceConfig
    ) -> DiscoveredJob | None:
        """Convert a WelcomeKit job payload into a discovered job."""
        title = clean_text(raw.get("title"))
        url = clean_text(raw.get("url") or raw.get("jobUrl"))
        if not title or not url:
            return None

        location = self._location_name(raw.get("location"))
        description = clean_text(raw.get("description")) or strip_html(
            raw.get("description_html")
        )
        contract_type = raw.get("contract_type") or {}
        employment_type = (
            clean_text(contract_type.get("text") or contract_type.get("label"))
            if isinstance(contract_type, dict)
            else clean_text(contract_type)
        )
        company_raw = raw.get("company") or {}
        company = (
            clean_text(company_raw.get("name"))
            if isinstance(company_raw, dict)
            else clean_text(company_raw)
        )

        return DiscoveredJob(
            external_id=clean_text(raw.get("id") or raw.get("slug")),
            url=url,
            title=title,
            company=company or source.config.get("company") or self._org_slug(source),
            location=location,
            description=description,
            department=clean_text(raw.get("department")),
            employment_type=employment_type,
            remote_status=self._detect_remote(raw),
            requirements=None,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=parse_datetime(raw.get("published_at")),
        )

    def _location_name(self, location: Any) -> str | None:  # noqa: ANN401
        """Build a location string from WelcomeKit location fields."""
        if not isinstance(location, dict):
            return clean_text(location) if location else None
        city = clean_text(location.get("city"))
        country = clean_text(location.get("country"))
        if city and country:
            return f"{city}, {country}"
        return city or country

    def _detect_remote(self, raw: dict[str, Any]) -> str | None:
        """Detect remote status from location or title fields."""
        if raw.get("remote") is True:
            return "remote"
        text = f"{raw.get('location')} {raw.get('title')}".lower()
        if "remote" in text:
            return "remote"
        if "hybrid" in text:
            return "hybrid"
        return None
