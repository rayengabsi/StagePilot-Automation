from __future__ import annotations

import pytest
from app.config.ai_config import TailoringQualityConfig
from app.domain.ai.quality import QualityCategory, QualitySeverity
from app.domain.master_profile.entities import (
    Certification,
    Education,
    Experience,
    MasterProfile,
    PersonalInfo,
    Skill,
)
from app.services.ai_tailoring_evaluator import AITailoringEvaluator


@pytest.fixture
def evaluator() -> AITailoringEvaluator:
    return AITailoringEvaluator(
        config=TailoringQualityConfig(enabled=True, minimum_quality_score=60.0)
    )


@pytest.fixture
def profile() -> MasterProfile:
    return MasterProfile(
        personal_info=PersonalInfo(full_name="John Doe", email="john@example.com"),
        education=(Education(institution="MIT", degree="BSc", field_of_study="CS"),),
        experience=(Experience(company="Acme", title="SWE"),),
        skills=(Skill(name="Python"), Skill(name="FastAPI")),
        certifications=(Certification(name="AWS Certified"),),
    )


GOOD_SECTIONS = {
    "summary": "Backend engineer specializing in Python and FastAPI APIs.",
    "skills": "Python, FastAPI, SQL",
    "experience": "Built REST APIs with FastAPI at Acme.",
    "projects": "Built a data pipeline with Docker.",
}


def test_good_resume_scores_high_and_no_revision(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    report = evaluator.evaluate_resume(
        GOOD_SECTIONS, profile, "Python FastAPI SQL Docker developer"
    )
    assert report.overall_score >= 80.0
    assert report.overall_quality in ("excellent", "good")
    assert report.needs_revision is False
    assert report.document_type == "resume"


def test_all_categories_present(evaluator: AITailoringEvaluator, profile: MasterProfile) -> None:
    report = evaluator.evaluate_resume(
        GOOD_SECTIONS, profile, "Python FastAPI SQL Docker developer"
    )
    expected = {cat.value for cat in QualityCategory}
    assert set(report.category_scores) == expected
    for score in report.category_scores.values():
        assert 0.0 <= score <= 100.0
    assert 0.0 <= report.overall_score <= 100.0


def test_disabled_config_returns_neutral(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    disabled = AITailoringEvaluator(
        config=TailoringQualityConfig(enabled=False, minimum_quality_score=60.0)
    )
    report = disabled.evaluate_resume({}, profile)
    assert report.overall_score == 100.0
    assert report.needs_revision is False
    assert report.issues == ()


def test_missing_job_keywords_reduce_coverage(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    report = evaluator.evaluate_resume(
        GOOD_SECTIONS, profile, "Python FastAPI SQL Docker developer"
    )
    assert report.category_scores[QualityCategory.KEYWORD_COVERAGE.value] < 100.0
    assert any("docker" in i.message for i in report.issues)


def test_empty_job_description_is_neutral(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    report = evaluator.evaluate_resume(GOOD_SECTIONS, profile, "")
    assert report.category_scores[QualityCategory.KEYWORD_COVERAGE.value] == 100.0


def test_missing_profile_facts_warn(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["skills"] = "SQL"
    sections["experience"] = "Built apps at Unknown Corp."
    report = evaluator.evaluate_resume(sections, profile, "Python FastAPI")
    assert report.category_scores[QualityCategory.FACTUAL_PRESERVATION.value] < 100.0


def test_invented_skill_detected(evaluator: AITailoringEvaluator) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["skills"] = "Python, Hadoop, Kafka"
    report = evaluator.evaluate_resume(sections, None, "Python developer")
    hallucination_issues = [i for i in report.issues if i.category == QualityCategory.HALLUCINATION]
    assert any("hadoop" in i.message for i in hallucination_issues)
    assert any("kafka" in i.message for i in hallucination_issues)


def test_invented_employer_detected(evaluator: AITailoringEvaluator) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["experience"] = "Worked at Google on search infrastructure."
    report = evaluator.evaluate_resume(sections, profile, "Python")
    assert any("google" in i.message for i in report.issues)


def test_known_employer_not_flagged(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["experience"] = "Built REST APIs with FastAPI at Acme."
    report = evaluator.evaluate_resume(sections, profile, "Python")
    assert not any("acme" in i.message for i in report.issues)


def test_education_hallucination_when_no_education(evaluator: AITailoringEvaluator) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["summary"] = "Holds a PhD in Computer Science from Harvard."
    report = evaluator.evaluate_resume(sections, None, "Python")
    assert any("education" in i.message for i in report.issues)


def test_degree_without_profile_institution_warns(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["summary"] = "Completed a PhD at Harvard University."
    report = evaluator.evaluate_resume(sections, profile, "Python")
    assert any("institution" in i.message for i in report.issues)


def test_placeholder_detected(evaluator: AITailoringEvaluator, profile: MasterProfile) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["projects"] = "TODO: add project"
    report = evaluator.evaluate_resume(sections, profile, "Python")
    assert report.category_scores[QualityCategory.GRAMMAR_FORMAT.value] < 100.0
    assert any("placeholder" in i.message.lower() for i in report.issues)


def test_short_terse_text_warns(evaluator: AITailoringEvaluator) -> None:
    sections = {
        "summary": "Dev",
        "skills": "SQL",
        "experience": "Apps",
        "projects": "",
    }
    report = evaluator.evaluate_resume(sections, None, "")
    assert report.category_scores[QualityCategory.GRAMMAR_FORMAT.value] < 100.0


def test_missing_section_reduces_completeness(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["projects"] = ""
    report = evaluator.evaluate_resume(sections, profile, "Python")
    assert report.category_scores[QualityCategory.SECTION_COMPLETENESS.value] < 100.0
    assert any("projects" in i.message for i in report.issues)


def test_cover_letter_complete(evaluator: AITailoringEvaluator, profile: MasterProfile) -> None:
    body = (
        "Dear Hiring Manager,\n\n"
        "I am a Python and FastAPI backend engineer with experience at Acme. "
        "I would love to bring my skills to your team and deliver high quality software. "
        "Thank you for considering my application.\n\nSincerely, John Doe"
    )
    report = evaluator.evaluate_cover_letter(body, profile, keywords=("python", "fastapi"))
    assert report.document_type == "cover_letter"
    assert report.category_scores[QualityCategory.SECTION_COMPLETENESS.value] == 100.0


def test_cover_letter_missing_greeting_and_closing(evaluator: AITailoringEvaluator) -> None:
    body = (
        "I am a backend engineer with strong Python and FastAPI skills and experience "
        "building production APIs at Acme. I am confident I can contribute immediately. "
        "This is a longer body to satisfy the minimum length requirement for a paragraph."
    )
    report = evaluator.evaluate_cover_letter(body, None, keywords=("python",))
    assert report.category_scores[QualityCategory.SECTION_COMPLETENESS.value] < 100.0


def test_cover_letter_missing_candidate_name(
    evaluator: AITailoringEvaluator, profile: MasterProfile
) -> None:
    body = (
        "Dear Hiring Manager,\n\n"
        "I am excited to apply with my Python and FastAPI experience built at Acme. "
        "I am confident I can deliver strong results for your engineering team. "
        "Thank you for your time and consideration.\n\nSincerely, Hiring Manager"
    )
    report = evaluator.evaluate_cover_letter(body, profile, keywords=("python", "fastapi"))
    assert report.category_scores[QualityCategory.FACTUAL_PRESERVATION.value] < 100.0


def test_ats_density_low_keyword_density_warns(evaluator: AITailoringEvaluator) -> None:
    filler = (
        "I am a professional who enjoys solving problems and working with colleagues. "
        "I focus on delivering value every single day and learning new things. "
        "My approach is to communicate clearly and to collaborate across teams. "
        "I take pride in my work and always aim for high quality outcomes. "
        "I believe that consistency and dedication matter the most in any role. "
        "I am always ready to help others and to grow with the organization. "
    )
    sections = {
        "summary": filler,
        "skills": "Python",
        "experience": filler,
        "projects": filler,
    }
    report = evaluator.evaluate_resume(sections, None, "Python")
    density_issues = [i for i in report.issues if i.category == QualityCategory.ATS_KEYWORD_DENSITY]
    assert report.category_scores[QualityCategory.ATS_KEYWORD_DENSITY.value] < 100.0
    assert any("density" in i.message for i in density_issues)


def test_below_threshold_marks_revision(evaluator: AITailoringEvaluator) -> None:
    sections = {
        "summary": "Worked at Google on Kubernetes",
        "skills": "Hadoop, Kafka",
        "experience": "Held a PhD from Harvard",
        "projects": "TODO",
    }
    report = evaluator.evaluate_resume(sections, None, "Python developer")
    assert report.needs_revision is True
    assert report.overall_quality == "needs_revision"
    assert any("threshold" in s for s in report.suggestions)


def test_threshold_from_config() -> None:
    strict = AITailoringEvaluator(
        config=TailoringQualityConfig(enabled=True, minimum_quality_score=96.0)
    )
    report = strict.evaluate_resume(GOOD_SECTIONS, None, "Python FastAPI SQL Docker developer")
    assert report.needs_revision is True
    loose = AITailoringEvaluator(
        config=TailoringQualityConfig(enabled=True, minimum_quality_score=20.0)
    )
    report2 = loose.evaluate_resume(GOOD_SECTIONS, None, "Python FastAPI SQL Docker developer")
    assert report2.needs_revision is False


def test_suggestions_are_actionable(evaluator: AITailoringEvaluator) -> None:
    sections = {
        "summary": "Worked at Google on Kubernetes",
        "skills": "Hadoop",
        "experience": "Held a PhD from Harvard",
        "projects": "TODO",
    }
    report = evaluator.evaluate_resume(sections, None, "Python developer")
    assert len(report.suggestions) >= 1
    assert all(isinstance(s, str) and s for s in report.suggestions)


def test_issue_severity_error_for_hallucinations(evaluator: AITailoringEvaluator) -> None:
    sections = dict(GOOD_SECTIONS)
    sections["skills"] = "Python, Hadoop"
    report = evaluator.evaluate_resume(sections, None, "Python")
    hallucination_issues = [i for i in report.issues if i.category == QualityCategory.HALLUCINATION]
    assert hallucination_issues
    assert all(i.severity == QualitySeverity.ERROR for i in hallucination_issues)


def test_default_config_loads_from_toml() -> None:
    from app.config.ai_config import get_ai_config

    cfg = get_ai_config().tailoring_quality
    assert cfg.enabled is True
    assert cfg.minimum_quality_score == 60.0
