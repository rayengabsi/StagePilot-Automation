from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text, parse_epoch_millis
from app.shared.time import utc_now

_LEVER_API = "https://api.lever.co/v0/postings/{company}"
_PAGE_SIZE = 100


class LeverConnector(BaseJobSourceConnector):
    """Fetch public Lever postings via the Lever postings API."""

    source_type: ClassVar[JobSourceType] = JobSourceType.LEVER
    provider_name: ClassVar[str] = "lever"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that a Lever company slug is available."""
        errors = super().validate(source)
        if not self._company_slug(source):
            errors.append("lever company slug is required (config.company or base_url path)")
        return errors

    def _company_slug(self, source: JobSourceConfig) -> str | None:
        """Determine the Lever company slug from config or base_url."""
        slug = source.config.get("company")
        if slug:
            return str(slug)
        path = urlparse(source.base_url).path.strip("/")
        if path:
            return path.split("/")[-1]
        return None

    def _initial_cursor(self, source: JobSourceConfig) -> int:  # noqa: ARG002
        """Lever pagination starts at offset 0."""
        return 0

    def _fetch_page(self, source: JobSourceConfig, cursor: int) -> PageResult:
        """Fetch one page of Lever postings."""
        slug = self._company_slug(source)
        if slug is None:
            raise SourceConfigError("lever company slug is required")
        url = _LEVER_API.format(company=slug)
        data = self._http.get_json(
            url, params={"mode": "json", "limit": _PAGE_SIZE, "offset": cursor}
        )
        if not isinstance(data, list):
            return PageResult(items=[], next_cursor=None)
        next_cursor = cursor + _PAGE_SIZE if len(data) >= _PAGE_SIZE else None
        return PageResult(items=data, next_cursor=next_cursor)

    def normalize(self, raw: dict[str, Any], source: JobSourceConfig) -> DiscoveredJob | None:
        """Convert a Lever posting payload into a discovered job."""
        title = clean_text(raw.get("text"))
        url = clean_text(raw.get("hostedUrl"))
        if not title or not url:
            return None

        categories = raw.get("categories") or {}
        if not isinstance(categories, dict):
            categories = {}
        location = clean_text(categories.get("location"))
        department = clean_text(categories.get("team") or categories.get("department"))

        description = clean_text(raw.get("descriptionPlain"))
        requirements = self._build_requirements(raw.get("lists"))
        remote_status = self._detect_remote(description)

        return DiscoveredJob(
            external_id=clean_text(raw.get("id")),
            url=url,
            title=title,
            company=source.config.get("company") or self._company_slug(source),
            location=location,
            description=description,
            department=department,
            employment_type=clean_text(categories.get("commitment")),
            remote_status=remote_status,
            requirements=requirements,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=parse_epoch_millis(raw.get("createdAt")),
        )

    def _build_requirements(self, lists: Any) -> str | None:  # noqa: ANN401
        """Assemble requirement bullets from Lever's lists structure."""
        if not isinstance(lists, list) or not lists:
            return None
        bullets: list[str] = []
        for section in lists:
            if not isinstance(section, dict):
                continue
            content = section.get("content")
            if isinstance(content, str) and content.strip():
                bullets.append(content.strip())
        return "\n".join(bullets) if bullets else None

    def _detect_remote(self, description: str | None) -> str | None:
        """Detect remote status from the description text."""
        if not description:
            return None
        lowered = description.lower()
        if "remote" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        return None
