from __future__ import annotations

from app.domain.ai.quality import (
    QualityCategory,
    QualityIssue,
    QualityReport,
    QualitySeverity,
)


def _sample_report() -> QualityReport:
    return QualityReport(
        document_type="resume",
        category_scores={"keyword_coverage": 80.0, "hallucination": 100.0},
        overall_score=88.5,
        overall_quality="good",
        needs_revision=False,
        issues=(
            QualityIssue(
                category=QualityCategory.KEYWORD_COVERAGE,
                severity=QualitySeverity.WARNING,
                message="Job keywords missing: docker",
            ),
        ),
        suggestions=("Mention docker.",),
    )


def test_quality_issue_to_dict() -> None:
    issue = QualityIssue(
        category=QualityCategory.HALLUCINATION,
        severity=QualitySeverity.ERROR,
        message="Skill not in profile: 'hadoop'",
    )
    d = issue.to_dict()
    assert d["category"] == "hallucination"
    assert d["severity"] == "error"
    assert d["message"] == "Skill not in profile: 'hadoop'"


def test_quality_report_to_dict() -> None:
    d = _sample_report().to_dict()
    assert d["document_type"] == "resume"
    assert d["category_scores"]["keyword_coverage"] == 80.0
    assert d["overall_score"] == 88.5
    assert d["overall_quality"] == "good"
    assert d["needs_revision"] is False
    assert d["issues"][0]["category"] == "keyword_coverage"
    assert d["suggestions"] == ["Mention docker."]


def test_quality_report_defaults() -> None:
    report = QualityReport(
        document_type="cover_letter",
        category_scores={},
        overall_score=100.0,
        overall_quality="excellent",
        needs_revision=False,
    )
    assert report.issues == ()
    assert report.suggestions == ()
    d = report.to_dict()
    assert d["issues"] == []
    assert d["suggestions"] == []


def test_category_enum_values() -> None:
    values = {c.value for c in QualityCategory}
    assert values == {
        "keyword_coverage",
        "factual_preservation",
        "hallucination",
        "grammar_format",
        "section_completeness",
        "ats_keyword_density",
    }
