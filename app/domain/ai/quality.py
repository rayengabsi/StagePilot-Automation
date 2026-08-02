from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class QualityCategory(StrEnum):
    """Scoring categories of the AI tailoring quality evaluation."""

    KEYWORD_COVERAGE = "keyword_coverage"
    FACTUAL_PRESERVATION = "factual_preservation"
    HALLUCINATION = "hallucination"
    GRAMMAR_FORMAT = "grammar_format"
    SECTION_COMPLETENESS = "section_completeness"
    ATS_KEYWORD_DENSITY = "ats_keyword_density"


class QualitySeverity(StrEnum):
    """Severity of a detected quality issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """A single deterministic quality finding."""

    category: QualityCategory
    severity: QualitySeverity
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Structured quality report for a generated document.

    Contains per-category scores (0-100), an overall tailoring quality score,
    a derived quality level, the revision decision, and actionable findings.
    """

    document_type: str
    category_scores: dict[str, float]
    overall_score: float
    overall_quality: str
    needs_revision: bool
    issues: tuple[QualityIssue, ...] = ()
    suggestions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type,
            "category_scores": dict(self.category_scores),
            "overall_score": self.overall_score,
            "overall_quality": self.overall_quality,
            "needs_revision": self.needs_revision,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": list(self.suggestions),
        }
