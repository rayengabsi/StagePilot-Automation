from __future__ import annotations

import re
from typing import ClassVar

from bs4 import BeautifulSoup

from app.domain.jobs.entities import DiscoveredJob, NormalizedJob
from app.domain.jobs.errors import JobNormalizationError


class JobNormalizationService:
    """Normalize discovered job listings into canonical job records."""

    _MAX_LENGTHS: ClassVar[dict[str, int]] = {
        "title": 500,
        "company": 255,
        "location": 255,
        "department": 255,
        "employment_type": 100,
        "remote_status": 50,
    }

    def normalize(self, job: DiscoveredJob) -> NormalizedJob:
        """Normalize one discovered job."""
        title = self._clean_text(job.title)
        url = self._clean_text(job.url)

        if not title:
            raise JobNormalizationError("Discovered job is missing a title.")
        if not url:
            raise JobNormalizationError("Discovered job is missing a URL.")

        normalized = NormalizedJob(
            external_id=self._clean_optional_text(job.external_id),
            url=url,
            title=title,
            company=self._clean_optional_text(job.company),
            location=self._clean_optional_text(job.location),
            description=self._clean_optional_html(job.description),
            requirements=self._clean_optional_text(job.requirements),
            posted_at=job.posted_at,
            department=self._clean_optional_text(job.department),
            employment_type=self._clean_optional_text(job.employment_type),
            remote_status=self._clean_optional_text(job.remote_status),
        )
        self._validate_field_lengths(normalized)
        return normalized

    def _validate_field_lengths(self, job: NormalizedJob) -> None:
        """Reject jobs whose fields exceed the database column limits."""
        for field_name, max_len in self._MAX_LENGTHS.items():
            value: str | None = getattr(job, field_name)
            if value is not None and len(value) > max_len:
                raise JobNormalizationError(
                    f"Field '{field_name}' exceeds maximum length of {max_len}"
                )

    def _clean_optional_html(self, value: str | None) -> str | None:
        """Clean optional HTML-rich text into readable plain text."""
        if value is None:
            return None
        text = BeautifulSoup(value, "html.parser").get_text(" ")
        return self._clean_optional_text(text)

    def _clean_optional_text(self, value: str | None) -> str | None:
        """Clean optional text and convert blanks to None."""
        if value is None:
            return None
        cleaned = self._clean_text(value)
        return cleaned or None

    def _clean_text(self, value: str) -> str:
        """Trim text and collapse repeated whitespace."""
        return re.sub(r"\s+", " ", value).strip()
