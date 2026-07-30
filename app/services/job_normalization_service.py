from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.domain.jobs.entities import DiscoveredJob, NormalizedJob
from app.domain.jobs.errors import JobNormalizationError


class JobNormalizationService:
    """Normalize discovered job listings into canonical job records."""

    def normalize(self, job: DiscoveredJob) -> NormalizedJob:
        """Normalize one discovered job."""
        title = self._clean_text(job.title)
        url = self._clean_text(job.url)

        if not title:
            raise JobNormalizationError("Discovered job is missing a title.")
        if not url:
            raise JobNormalizationError("Discovered job is missing a URL.")

        return NormalizedJob(
            external_id=self._clean_optional_text(job.external_id),
            url=url,
            title=title,
            company=self._clean_optional_text(job.company),
            location=self._clean_optional_text(job.location),
            description=self._clean_optional_html(job.description),
            requirements=None,
            posted_at=job.posted_at,
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
