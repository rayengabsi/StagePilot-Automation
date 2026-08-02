"""Deterministic extraction-quality benchmark for ``ProfileNormalizer``.

Runs every resume fixture in :mod:`tests.benchmark.fixtures` through the
normalizer and compares the extracted profile against the fixture's expected
ground truth. Produces a per-fixture, per-category report plus aggregate
percentages so extraction quality can be measured and tracked over time.

Run directly::

    python -m tests.benchmark.quality_report

Or import :func:`run_benchmark` for programmatic use (used by the regression
tests in ``test_benchmark.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.master_profile.entities import MasterProfile
from app.services.profile_normalizer import ProfileNormalizer

from .fixtures import Fixture, load_fixtures

# Personal fields compared for exact value match (None matches None/empty).
PERSONAL_FIELDS = (
    "full_name",
    "email",
    "phone",
    "location",
    "nationality",
    "linkedin_url",
    "github_url",
    "portfolio_url",
)

# Per-entry comparison rules: profile attribute -> expected key.
ENTRY_CHECKS = (("education", "education"), ("experience", "experience"), ("projects", "projects"))

COUNT_FIELDS = (
    "education_count",
    "experience_count",
    "projects_count",
    "languages_count",
    "certifications_count",
    "awards_count",
    "publications_count",
)

REPORT_CATEGORIES = (
    *PERSONAL_FIELDS,
    "summary",
    "education",
    "experience",
    "projects",
    "skills",
    "languages",
    "certifications",
    "awards",
    "publications",
)


@dataclass
class FixtureResult:
    name: str
    passed: bool = True
    details: list[str] = field(default_factory=list)
    checks: dict[str, list[bool]] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    per_fixture: list[FixtureResult] = field(default_factory=list)

    @property
    def overall(self) -> float:
        total = matched = 0
        for fixture_result in self.per_fixture:
            for results in fixture_result.checks.values():
                matched += sum(results)
                total += len(results)
        return (matched / total * 100.0) if total else 100.0

    def category_percentage(self, category: str) -> float:
        matched = total = 0
        for fixture_result in self.per_fixture:
            results = fixture_result.checks.get(category, [])
            matched += sum(results)
            total += len(results)
        return (matched / total * 100.0) if total else 100.0


def _value_matches(expected: str | int | None, actual: str | None) -> bool:
    if expected is None:
        return actual is None or actual == ""
    return str(expected).strip().lower() == str(actual).strip().lower()


def _summary_matches(expected: str | None, actual: str | None) -> bool:
    if not expected:
        return True
    return bool(actual) and expected.lower() in (actual or "").lower()


def _entry_ok(profile: MasterProfile, attr: str, expected_entries: list[dict]) -> list[bool]:
    actual_entries = getattr(profile, attr)
    results: list[bool] = []
    for index, expected in enumerate(expected_entries):
        if index >= len(actual_entries):
            results.append(False)
            continue
        actual = actual_entries[index]
        results.append(
            all(
                _value_matches(value, getattr(actual, field_name))
                for field_name, value in expected.items()
            )
        )
    return results


def evaluate_fixture(normalizer: ProfileNormalizer, fixture: Fixture) -> FixtureResult:
    result = FixtureResult(name=fixture["name"])
    expected = fixture["expected"]
    profile = normalizer.normalize(fixture["text"])

    def record(category: str, ok: bool, label: str) -> None:
        result.checks.setdefault(category, []).append(ok)
        if not ok:
            result.passed = False
            result.details.append(label)

    for category in PERSONAL_FIELDS:
        if category in expected:
            actual = getattr(profile.personal_info, category)
            label = f"{category}={expected[category]!r}"
            record(category, _value_matches(expected[category], actual), label)

    if "summary_contains" in expected:
        record(
            "summary",
            _summary_matches(expected["summary_contains"], profile.personal_info.summary),
            f"summary contains {expected['summary_contains']!r}",
        )

    for attr, expected_key in ENTRY_CHECKS:
        entries = expected.get(expected_key, [])
        for index, ok in enumerate(_entry_ok(profile, attr, entries)):
            record(expected_key, ok, f"{expected_key}[{index}]")

    for count_field in COUNT_FIELDS:
        if count_field in expected:
            attr = count_field.replace("_count", "")
            ok = len(getattr(profile, attr)) == expected[count_field]
            record(attr, ok, count_field)

    if "skills_min" in expected:
        record("skills", len(profile.skills) >= expected["skills_min"], "skills_min")

    return result


def run_benchmark(fixtures: list[Fixture] | None = None) -> BenchmarkReport:
    normalizer = ProfileNormalizer()
    report = BenchmarkReport()
    for fixture in fixtures or load_fixtures():
        report.per_fixture.append(evaluate_fixture(normalizer, fixture))
    return report


def print_report(report: BenchmarkReport) -> None:
    print("Extraction quality benchmark")
    print("=" * 50)
    for fixture_result in report.per_fixture:
        status = "PASS" if fixture_result.passed else "FAIL"
        print(f"[{status}] {fixture_result.name}")
        for detail in fixture_result.details:
            print(f"       missing/mismatch: {detail}")
    print("-" * 50)
    for category in REPORT_CATEGORIES:
        pct = report.category_percentage(category)
        if pct is not None:
            print(f"{category:<18} {pct:5.1f}%")
    print("-" * 50)
    print(f"{'overall':<18} {report.overall:5.1f}%")


if __name__ == "__main__":
    print_report(run_benchmark())
