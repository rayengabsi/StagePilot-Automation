"""Unit tests for carrying rich parsed fields onto the notify result and card.

Verifies the payload → result mapping helpers and the serialized result shape,
so the Telegram card can rely on the enriched fields being present.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.linkedin_mcp_pipeline_service import (
    LinkedInMCPRecommendationResult,
    _payload_str,
    _raw_payload,
)


def test_raw_payload_returns_dict_or_empty() -> None:
    raw = SimpleNamespace(raw_payload_json={"salary": "$80K - $100K"})
    job = SimpleNamespace(raw_job=raw)
    assert _raw_payload(job) == {"salary": "$80K - $100K"}
    assert _raw_payload(None) == {}
    assert _raw_payload(SimpleNamespace(raw_job=None)) == {}
    assert _raw_payload(SimpleNamespace(raw_job=SimpleNamespace(raw_payload_json=None))) == {}


def test_payload_str_coerces_and_drops_empty() -> None:
    assert _payload_str({"salary": "x"}, "salary") == "x"
    assert _payload_str({"salary": 1000}, "salary") == "1000"
    assert _payload_str({"salary": None}, "salary") is None
    assert _payload_str({"salary": ""}, "salary") is None
    assert _payload_str({}, "salary") is None


def test_result_to_dict_includes_rich_fields() -> None:
    result = LinkedInMCPRecommendationResult(
        job_id=1,
        title="Engineer",
        company="Acme",
        location="Tunis",
        url="https://x",
        final_score=50.0,
        status="active",
        above_threshold=True,
        explanation="why",
        matched_skills=("Python",),
        missing_skills=(),
        salary="$80K - $100K",
        employment_type="Full-time",
        experience_level="Senior",
        company_size="51-200",
        recruiter="Jane",
        posted_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    data = result.to_dict()
    assert data["salary"] == "$80K - $100K"
    assert data["employment_type"] == "Full-time"
    assert data["experience_level"] == "Senior"
    assert data["company_size"] == "51-200"
    assert data["recruiter"] == "Jane"
    assert data["posted_at"] == "2026-08-01T00:00:00+00:00"


def test_result_to_dict_omits_absent_rich_fields() -> None:
    result = LinkedInMCPRecommendationResult(
        job_id=1,
        title="Engineer",
        company="Acme",
        location="Tunis",
        url="https://x",
        final_score=50.0,
        status="active",
        above_threshold=True,
        explanation="why",
        matched_skills=(),
        missing_skills=(),
    )
    data = result.to_dict()
    assert data["salary"] is None
    assert data["posted_at"] is None
    assert data["recruiter"] is None
