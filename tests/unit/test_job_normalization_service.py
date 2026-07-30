from __future__ import annotations

from app.domain.jobs.entities import DiscoveredJob
from app.services.job_normalization_service import JobNormalizationService
from app.shared.time import utc_now


def test_normalize_discovered_job_cleans_text_and_html() -> None:
    """Normalizer should trim text, collapse whitespace, and strip HTML descriptions."""
    discovered = DiscoveredJob(
        external_id=" job-1 ",
        url=" https://example.com/jobs/1 ",
        title=" Software   Internship ",
        company=" Example  Company ",
        location=" Remote ",
        description="<p>Build   APIs</p>",
        raw_payload={},
        discovered_at=utc_now(),
    )

    normalized = JobNormalizationService().normalize(discovered)

    assert normalized.title == "Software Internship"
    assert normalized.company == "Example Company"
    assert normalized.description == "Build APIs"
