from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_datetime, strip_html
from app.shared.time import utc_now

_SMART_RECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{company}/postings"
_PAGE_SIZE = 100


class SmartRecruitersConnector(BaseJobSourceConnector):
    """Fetch public SmartRecruiters company postings."""

    source_type: ClassVar[JobSourceType] = JobSourceType.SMART_RECRUITERS
    provider_name: ClassVar[str] = "smart_recruiters"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that a SmartRecruiters company alias is available."""
        errors = super().validate(source)
        if not self._company_alias(source):
            errors.append(
                "smartrecruiters company alias is required (config.company or base_url path)"
            )
        return errors

    def _company_alias(self, source: JobSourceConfig) -> str | None:
        """Determine the SmartRecruiters company alias."""
        alias = source.config.get("company")
        if alias:
            return str(alias)
        path = urlparse(source.base_url).path.strip("/")
        if path:
            return path.split("/")[-1]
        return None

    def _initial_cursor(self, source: JobSourceConfig) -> int:  # noqa: ARG002
        """SmartRecruiters pagination starts at offset 0."""
        return 0

    def _fetch_page(self, source: JobSourceConfig, cursor: int) -> PageResult:
        """Fetch one page of SmartRecruiters postings."""
        alias = self._company_alias(source)
        if alias is None:
            raise SourceConfigError("smartrecruiters company alias is required")
        url = _SMART_RECRUITERS_API.format(company=alias)
        data = self._http.get_json(url, params={"limit": _PAGE_SIZE, "offset": cursor})
        content = data.get("content") or []
        total_found = int(data.get("totalFound", 0) or 0)
        next_cursor = cursor + _PAGE_SIZE if content and cursor + _PAGE_SIZE < total_found else None
        return PageResult(items=content, next_cursor=next_cursor)

    def normalize(
        self, raw: dict[str, Any], source: JobSourceConfig
    ) -> DiscoveredJob | None:
        """Convert a SmartRecruiters posting into a discovered job."""
        title = clean_text(raw.get("name"))
        url = clean_text(raw.get("ref"))
        if not title:
            return None

        location = self._location_name(raw.get("location"))
        department_raw = raw.get("department") or {}
        department = (
            clean_text(department_raw.get("label"))
            if isinstance(department_raw, dict)
            else clean_text(department_raw)
        )
        description, requirements = self._extract_sections(raw.get("jobAd"))

        return DiscoveredJob(
            external_id=clean_text(raw.get("id")),
            url=url or source.base_url,
            title=title,
            company=source.config.get("company") or self._company_alias(source),
            location=location,
            description=description,
            department=department,
            employment_type=None,
            remote_status=self._detect_remote(location),
            requirements=requirements,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=parse_datetime(raw.get("releasedDate")),
        )

    def _location_name(self, location: Any) -> str | None:  # noqa: ANN401
        """Build a location string from SmartRecruiters location fields."""
        if not isinstance(location, dict):
            return clean_text(location) if location else None
        city = clean_text(location.get("city"))
        country = clean_text(location.get("country"))
        if city and country:
            return f"{city}, {country}"
        return city or country

    def _extract_sections(self, job_ad: Any) -> tuple[str | None, str | None]:  # noqa: ANN401
        """Extract description and requirements from jobAd sections."""
        if not isinstance(job_ad, dict):
            return None, None
        sections = job_ad.get("sections") or []
        description_parts: list[str] = []
        requirement_parts: list[str] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            text = strip_html(section.get("jobDescription"))
            if not text:
                continue
            title = (section.get("title") or "").lower()
            if "requirement" in title or "qualification" in title:
                requirement_parts.append(text)
            else:
                description_parts.append(text)
        description = "\n".join(description_parts) if description_parts else None
        requirements = "\n".join(requirement_parts) if requirement_parts else None
        return description, requirements

    def _detect_remote(self, location: str | None) -> str | None:
        """Detect remote status from location text."""
        if not location:
            return None
        lowered = location.lower()
        if "remote" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        return None
