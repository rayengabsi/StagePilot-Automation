from __future__ import annotations

import pytest
from app.domain.jobs.entities import DiscoveredJob
from app.domain.jobs.errors import JobNormalizationError
from app.services.job_normalization_service import JobNormalizationService
from app.shared.time import utc_now


def _make_discovered(**overrides: object) -> DiscoveredJob:
    """Build a DiscoveredJob with sensible defaults."""
    defaults = {
        "external_id": "job-1",
        "url": "https://example.com/jobs/1",
        "title": "Software Internship",
        "company": "Example",
        "location": "Remote",
        "description": "Build APIs",
        "raw_payload": {},
        "discovered_at": utc_now(),
    }
    defaults.update(overrides)
    return DiscoveredJob(**defaults)


def test_normalize_discovered_job_cleans_text_and_html() -> None:
    """Normalizer should trim text, collapse whitespace, and strip HTML descriptions."""
    discovered = _make_discovered(
        external_id=" job-1 ",
        url=" https://example.com/jobs/1 ",
        title=" Software   Internship ",
        company=" Example  Company ",
        location=" Remote ",
        description="<p>Build   APIs</p>",
    )

    normalized = JobNormalizationService().normalize(discovered)

    assert normalized.title == "Software Internship"
    assert normalized.company == "Example Company"
    assert normalized.description == "Build APIs"


def test_normalize_rejects_oversized_location() -> None:
    """A location exceeding 255 chars must be rejected before DB insert."""
    oversized = "x" * 256
    discovered = _make_discovered(location=oversized)

    with pytest.raises(JobNormalizationError, match="location"):
        JobNormalizationService().normalize(discovered)


def test_normalize_rejects_oversized_title() -> None:
    """A title exceeding 500 chars must be rejected."""
    oversized = "x" * 501
    discovered = _make_discovered(title=oversized)

    with pytest.raises(JobNormalizationError, match="title"):
        JobNormalizationService().normalize(discovered)


def test_normalize_rejects_oversized_company() -> None:
    """A company exceeding 255 chars must be rejected."""
    oversized = "x" * 256
    discovered = _make_discovered(company=oversized)

    with pytest.raises(JobNormalizationError, match="company"):
        JobNormalizationService().normalize(discovered)


def test_normalize_accepts_location_at_max_length() -> None:
    """A location at exactly 255 chars should be accepted."""
    max_len = "x" * 255
    discovered = _make_discovered(location=max_len)

    normalized = JobNormalizationService().normalize(discovered)
    assert normalized.location == max_len


def test_normalize_none_fields_skip_length_check() -> None:
    """None values for optional fields should not trigger length validation."""
    discovered = _make_discovered(company=None, location=None)

    normalized = JobNormalizationService().normalize(discovered)
    assert normalized.company is None
    assert normalized.location is None
