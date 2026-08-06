"""Milestone 2/3: LinkedIn MCP pipeline result serialization and explanations."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.linkedin_mcp_pipeline_service import (
    LinkedInMCPPipelineResult,
    LinkedInMCPPipelineService,
    LinkedInMCPRecommendationResult,
)


def _custom_explainer(rec: object, title: str, company: str) -> str:
    return f"{type(rec).__name__}: {title} at {company}"


def _recommendation_result() -> LinkedInMCPRecommendationResult:
    return LinkedInMCPRecommendationResult(
        job_id=1,
        title="Software Engineer Intern (PFE)",
        company="Acme Tech",
        location="Tunis, Tunisia",
        url="https://www.linkedin.com/jobs/view/mock-101",
        final_score=41.0,
        status="active",
        above_threshold=True,
        explanation="Matches your profile.",
        matched_skills=("Python",),
        missing_skills=(),
    )


def test_recommendation_result_to_dict_contains_location() -> None:
    data = _recommendation_result().to_dict()
    assert data["location"] == "Tunis, Tunisia"
    assert data["title"] == "Software Engineer Intern (PFE)"
    assert data["final_score"] == 41.0
    assert data["above_threshold"] is True
    assert data["matched_skills"] == ["Python"]
    assert data["missing_skills"] == []


def test_pipeline_result_to_dict_contains_all_counts() -> None:
    result = LinkedInMCPPipelineResult(
        source_id=1,
        source_name="LinkedIn Fake",
        cutoff=30.0,
        fetched=2,
        inserted=2,
        duplicates=0,
        rejected=0,
        matched_total=2,
        above_threshold=1,
        below_threshold=1,
        recommendations=(_recommendation_result(),),
    )
    data = result.to_dict()
    assert data["source_id"] == 1
    assert data["source_name"] == "LinkedIn Fake"
    assert data["threshold"] == 30.0
    assert data["fetched"] == 2
    assert data["matched_total"] == 2
    assert data["above_threshold"] == 1
    assert data["below_threshold"] == 1
    assert len(data["recommendations"]) == 1


def test_explain_uses_injected_explainer() -> None:
    service = LinkedInMCPPipelineService(
        session=MagicMock(),
        settings=MagicMock(),
        explainer=_custom_explainer,
    )
    text = service._explain(MagicMock(), "Software Engineer Intern (PFE)", "Acme Tech")
    assert text == "MagicMock: Software Engineer Intern (PFE) at Acme Tech"


def test_explain_default_builds_deterministic_narrative() -> None:
    service = LinkedInMCPPipelineService(session=MagicMock(), settings=MagicMock())
    rec = MagicMock()
    rec.final_score = 41.0
    rec.matched_detail.matched_skills = ["Python"]
    rec.matched_detail.missing_skills = ["Java"]
    rec.insights = None

    text = service._explain(rec, "Software Engineer Intern (PFE)", "Acme Tech")

    assert "Software Engineer Intern (PFE) at Acme Tech" in text
    assert "41.0" in text
    assert "Matched skills: Python." in text
    assert "Missing skills: Java." in text


def test_explain_default_appends_insights_summary() -> None:
    service = LinkedInMCPPipelineService(session=MagicMock(), settings=MagicMock())
    rec = MagicMock()
    rec.final_score = 30.0
    rec.matched_detail.matched_skills = []
    rec.matched_detail.missing_skills = []
    rec.insights.summary = "Insight summary text."

    text = service._explain(rec, "Title", "Company")

    assert text.endswith("Insight summary text.")
