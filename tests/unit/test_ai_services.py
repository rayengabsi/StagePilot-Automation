from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.domain.ai.entities import CoverLetter, EmailDraft, ExplanationResult, TailoredResume
from app.domain.ai.enums import AIFeature
from app.domain.master_profile.entities import (
    Education,
    Experience,
    Language,
    MasterProfile,
    PersonalInfo,
    Preference,
    Skill,
)
from app.domain.recommendation.entities import (
    HardRuleResult,
    MatchedDetail,
    Recommendation,
    ScoreBreakdown,
)
from app.domain.recommendation.enums import RecommendationStatus
from app.services.ai_orchestrator import AIOrchestrator
from app.services.cover_letter_service import CoverLetterService
from app.services.email_draft_service import EmailDraftService
from app.services.explanation_service import ExplanationService
from app.services.resume_tailor_service import ResumeTailorService


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    orchestrator = MagicMock(spec=AIOrchestrator)
    orchestrator.generate_text.return_value = (
        "This is a valid explanation text with sufficient length."
    )
    orchestrator.generate_json.return_value = {
        "summary": "Experienced Python developer with 5 years in web development.",
        "skills": "Python, FastAPI, SQL",
        "experience": "- Built REST APIs with FastAPI\n- Managed PostgreSQL databases",
        "projects": "- E-commerce platform\n- Data pipeline",
    }
    return orchestrator


@pytest.fixture
def sample_profile() -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe", email="john@example.com"),
        education=(Education(institution="MIT", degree="BSc", field_of_study="CS"),),
        experience=(Experience(company="Google", title="SWE", technologies=("Python",)),),
        skills=(Skill(name="Python"), Skill(name="SQL")),
        languages=(Language(name="English"),),
        preferences=Preference(),
    )


@pytest.fixture
def sample_recommendation() -> Recommendation:
    return Recommendation(
        profile_id=1,
        job_id=42,
        final_score=85.0,
        ranking_position=1,
        status=RecommendationStatus.ACTIVE,
        matched_detail=MatchedDetail(
            matched_skills=("Python", "SQL"),
            missing_skills=("Docker",),
            matched_technologies=("FastAPI",),
            missing_technologies=("Kubernetes",),
        ),
        score_breakdown=ScoreBreakdown(skills=100.0, technologies=80.0),
        hard_rule_result=HardRuleResult(passed=True),
    )


def test_explain_service_returns_result(
    mock_orchestrator: MagicMock, sample_recommendation: Recommendation
) -> None:
    svc = ExplanationService(orchestrator=mock_orchestrator)
    result = svc.explain(sample_recommendation, job_title="Engineer", company="Acme")
    assert isinstance(result, ExplanationResult)
    assert "explanation" in str(result.to_dict())


def test_explain_calls_orchestrator(
    mock_orchestrator: MagicMock, sample_recommendation: Recommendation
) -> None:
    svc = ExplanationService(orchestrator=mock_orchestrator)
    svc.explain(sample_recommendation)
    mock_orchestrator.generate_text.assert_called_once()
    _args, kwargs = mock_orchestrator.generate_text.call_args
    assert kwargs["prompt_name"] == "match_explanation"
    assert kwargs["feature"] == AIFeature.EXPLANATION


def test_tailor_service_returns_result(
    mock_orchestrator: MagicMock,
    sample_profile: MasterProfile,
    sample_recommendation: Recommendation,
) -> None:
    svc = ResumeTailorService(orchestrator=mock_orchestrator)
    result = svc.tailor(sample_profile, sample_recommendation, job_description="Python dev")
    assert isinstance(result, TailoredResume)
    assert "summary" in result.sections
    assert result.source_profile_version == "current"


def test_tailor_service_attaches_quality_report(
    mock_orchestrator: MagicMock,
    sample_profile: MasterProfile,
    sample_recommendation: Recommendation,
) -> None:
    svc = ResumeTailorService(orchestrator=mock_orchestrator)
    result = svc.tailor(sample_profile, sample_recommendation, job_description="Python dev")
    assert result.quality is not None
    assert result.quality.document_type == "resume"
    assert result.quality.overall_score >= 0.0
    assert "resume" in result.to_dict()["quality"]["document_type"]


def test_cover_letter_service_attaches_quality_report(
    mock_orchestrator: MagicMock,
    sample_profile: MasterProfile,
    sample_recommendation: Recommendation,
) -> None:
    svc = CoverLetterService(orchestrator=mock_orchestrator)
    result = svc.generate(sample_profile, sample_recommendation, company="Acme", recipient="HR")
    assert result.quality is not None
    assert result.quality.document_type == "cover_letter"
    assert result.to_dict()["quality"]["document_type"] == "cover_letter"


def test_tailor_calls_orchestrator(
    mock_orchestrator: MagicMock,
    sample_profile: MasterProfile,
    sample_recommendation: Recommendation,
) -> None:
    svc = ResumeTailorService(orchestrator=mock_orchestrator)
    svc.tailor(sample_profile, sample_recommendation)
    mock_orchestrator.generate_json.assert_called_once()
    _args, kwargs = mock_orchestrator.generate_json.call_args
    assert kwargs["prompt_name"] == "resume_tailoring"
    assert kwargs["feature"] == AIFeature.RESUME_TAILORING


def test_cover_letter_service_returns_result(
    mock_orchestrator: MagicMock,
    sample_profile: MasterProfile,
    sample_recommendation: Recommendation,
) -> None:
    svc = CoverLetterService(orchestrator=mock_orchestrator)
    result = svc.generate(sample_profile, sample_recommendation, company="Acme", recipient="HR")
    assert isinstance(result, CoverLetter)


def test_cover_letter_calls_orchestrator(
    mock_orchestrator: MagicMock,
    sample_profile: MasterProfile,
    sample_recommendation: Recommendation,
) -> None:
    svc = CoverLetterService(orchestrator=mock_orchestrator)
    svc.generate(sample_profile, sample_recommendation)
    mock_orchestrator.generate_text.assert_called_once()
    _args, kwargs = mock_orchestrator.generate_text.call_args
    assert kwargs["prompt_name"] == "cover_letter"


def test_email_draft_returns_result(mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.generate_json.return_value = {
        "subject": "Application for Engineer position",
        "body": "Dear Hiring Manager,\n\nI am writing to apply...",
        "signature": "John Doe",
    }
    svc = EmailDraftService(orchestrator=mock_orchestrator)
    cover = CoverLetter(body="I am a great fit.", recipient_name="HR", company_name="Acme")
    result = svc.draft(
        cover,
        company="Acme",
        job_title="Engineer",
        recipient="HR",
        candidate_name="John",
    )
    assert isinstance(result, EmailDraft)
    assert "subject" in str(result.to_dict())
    assert "body" in str(result.to_dict())


def test_email_draft_calls_orchestrator(mock_orchestrator: MagicMock) -> None:
    mock_orchestrator.generate_json.return_value = {
        "subject": "Application",
        "body": "Body text",
        "signature": "John",
    }
    svc = EmailDraftService(orchestrator=mock_orchestrator)
    cover = CoverLetter(body="Body.")
    svc.draft(cover)
    mock_orchestrator.generate_json.assert_called_once()
    _args, kwargs = mock_orchestrator.generate_json.call_args
    assert kwargs["prompt_name"] == "email_application"
    assert kwargs["feature"] == AIFeature.EMAIL_DRAFT
