from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.registry import build_connector_registry
from app.infrastructure.job_sources.validation import (
    NORMALIZED_JOB_SCHEMA,
    ConnectorValidator,
)


def _all_providers() -> list[str]:
    """Return the provider names registered for validation."""
    registry = build_connector_registry(Settings())
    return [connector.provider_name for connector in registry.all()]


def _validate_all() -> dict[str, Any]:
    """Benchmark every registered provider without a source config."""
    validator = ConnectorValidator(Settings())
    registry = build_connector_registry(Settings())
    return {
        connector.provider_name: validator.validate_connector(connector)
        for connector in registry.all()
    }


def test_normalized_job_schema_is_canonical() -> None:
    """The normalized job schema should cover the canonical field set."""
    assert NORMALIZED_JOB_SCHEMA == (
        "external_id",
        "url",
        "title",
        "company",
        "location",
        "description",
        "raw_payload",
        "discovered_at",
        "posted_at",
        "department",
        "employment_type",
        "remote_status",
        "requirements",
    )


def test_every_registered_provider_is_healthy() -> None:
    """All providers should pass their full scenario suite."""
    results = _validate_all()

    assert set(results) == set(_all_providers())
    for provider, result in results.items():
        assert result.status == "healthy", f"{provider}: {result.issues}"
        assert result.overall_score >= 80.0, provider


def test_benchmark_reports_perfect_metrics() -> None:
    """Nominal connectors should score 100% on every dimension."""
    results = _validate_all()

    for provider, result in results.items():
        assert result.success_rate == 1.0, provider
        assert result.normalization_quality == 1.0, provider
        assert result.error_handling == 1.0, provider
        assert result.duplicate_rate == 0.0, provider
        assert result.unhandled_errors == 0, provider
        assert result.issues == [], provider


def test_each_provider_exercises_multiple_scenarios() -> None:
    """Every provider should run nominal and adversarial scenarios."""
    results = _validate_all()

    for provider, result in results.items():
        assert result.scenarios_total >= 4, provider
        assert result.error_cases_total >= 1, provider
        assert result.jobs_produced >= 1, provider


def test_scenario_results_are_recorded() -> None:
    """Each scenario outcome should be captured on the benchmark result."""
    results = _validate_all()

    for provider, result in results.items():
        assert result.scenarios, provider
        outcomes = [scenario.outcome for scenario in result.scenarios]
        assert "success" in outcomes, provider
        assert "handled" in outcomes, provider


def test_result_to_dict_is_json_serializable() -> None:
    """Benchmark results should serialize to a plain JSON-safe dict."""
    import json

    results = _validate_all()
    provider = next(iter(results))

    payload = results[provider].to_dict()

    json.dumps(payload)
    assert payload["provider"] == provider
    assert isinstance(payload["issues"], list)
    assert 0.0 <= payload["overall_score"] <= 100.0


def test_connector_emits_canonical_schema_fields() -> None:
    """Every job produced should expose the canonical normalized fields."""
    validator = ConnectorValidator(Settings())
    registry = build_connector_registry(Settings())

    for connector in registry.all():
        result = validator.validate_connector(connector)
        for job in result.scenarios[0].jobs:
            for field in NORMALIZED_JOB_SCHEMA:
                assert hasattr(job, field), f"{connector.provider_name}: missing {field}"


def test_unknown_provider_returns_failed_result() -> None:
    """A connector without validation scenarios should report failed."""
    validator = ConnectorValidator(Settings())

    class _UnknownConnector:
        provider_name = "not_a_provider"

        def validate(self, source: JobSourceConfig) -> list[str]:
            return []

    result = validator.validate_connector(_UnknownConnector())  # type: ignore[arg-type]

    assert result.status == "failed"
    assert any("no validation scenarios" in issue for issue in result.issues)


def test_invalid_source_config_marks_result_failed() -> None:
    """A malformed source config should fail only that source."""
    registry = build_connector_registry(Settings())
    connector = registry.get(JobSourceType.GREENHOUSE)
    source = JobSourceConfig(
        id=99,
        name="Broken",
        type=JobSourceType.GREENHOUSE,
        base_url="https://boards.greenhouse.io",
        config={},
    )

    result = ConnectorValidator(Settings()).validate_connector(connector, source)

    assert result.source_id == 99
    assert result.source_name == "Broken"
    assert result.status == "failed"
    assert any("source config invalid" in issue for issue in result.issues)
