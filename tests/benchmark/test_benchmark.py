"""Regression guards for the extraction-quality benchmark.

These tests enforce the target extraction-quality thresholds from the phase-3
objective on the deterministic resume fixtures. A drop in extraction quality
fails the suite so regressions are caught immediately.
"""

from __future__ import annotations

import pytest

from .fixtures import load_fixtures
from .quality_report import run_benchmark

# Target thresholds (percentage of fixture checks that must pass per category).
TARGETS: dict[str, float] = {
    "full_name": 100.0,
    "email": 100.0,
    "phone": 100.0,
    "linkedin_url": 100.0,
    "github_url": 100.0,
    "portfolio_url": 95.0,
    "location": 100.0,
    "summary": 95.0,
    "education": 99.0,
    "experience": 98.0,
    "projects": 95.0,
    "skills": 95.0,
    "languages": 95.0,
    "certifications": 95.0,
    "awards": 95.0,
    "publications": 95.0,
}


def test_benchmark_fixtures_are_loadable() -> None:
    fixtures = load_fixtures()
    assert len(fixtures) >= 5
    names = {f["name"] for f in fixtures}
    assert len(names) == len(fixtures)
    for fixture in fixtures:
        assert fixture["text"].strip()
        assert fixture["expected"]


@pytest.mark.parametrize("category", sorted(TARGETS))
def test_extraction_quality_meets_target(category: str) -> None:
    report = run_benchmark()
    actual = report.category_percentage(category)
    assert actual >= TARGETS[category], (
        f"category {category!r} at {actual:.1f}%, below target {TARGETS[category]:.1f}%"
    )


def test_overall_extraction_quality_meets_target() -> None:
    report = run_benchmark()
    assert report.overall >= 95.0, f"overall extraction at {report.overall:.1f}%, below 95%"


def test_all_benchmark_fixtures_pass() -> None:
    report = run_benchmark()
    failed = [result for result in report.per_fixture if not result.passed]
    assert not failed, f"failed fixtures: {[f.name for f in failed]}"
