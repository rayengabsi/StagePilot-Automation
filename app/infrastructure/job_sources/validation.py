from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from app.config.settings import Settings
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import (
    DiscoveryError,
    SourceConfigError,
    SourceFetchError,
    SourceParseError,
)
from app.infrastructure.job_sources.base import BaseJobSourceConnector
from app.infrastructure.job_sources.rate_limiter import RateLimiter

# Canonical normalized job schema shared by every connector regardless of provider.
# Each connector must emit a DiscoveredJob exposing exactly these fields.
NORMALIZED_JOB_SCHEMA: tuple[str, ...] = (
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

_LATENCY_BUDGET_MS = 2000.0


@dataclass(frozen=True, slots=True)
class ConnectorScenario:
    """One mocked real-world scenario exercised against a connector.

    ``expected_count`` marks a nominal scenario: fetching the source must
    return exactly that many jobs without raising. ``expected_error`` and
    ``expect_validate_errors`` mark adversarial scenarios used to measure
    error handling.
    """

    name: str
    source: JobSourceConfig
    responder: Callable[..., Any]
    expected_count: int | None = None
    expected_fields: tuple[dict[str, Any], ...] | None = None
    expected_error: type[DiscoveryError] | None = None
    expect_validate_errors: bool = False


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Outcome of running one connector scenario."""

    name: str
    kind: str
    outcome: str
    latency_ms: float
    jobs_count: int
    error_type: str | None
    jobs: tuple[DiscoveredJob, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectorBenchmarkResult:
    """Validation metrics measured for one provider connector."""

    provider: str
    source_id: int | None = None
    source_name: str | None = None
    source_type: str | None = None
    scenarios_total: int = 0
    scenarios_succeeded: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    fields_checked: int = 0
    fields_matched: int = 0
    normalization_quality: float = 0.0
    jobs_produced: int = 0
    duplicate_jobs: int = 0
    duplicate_rate: float = 0.0
    error_cases_total: int = 0
    error_cases_handled: int = 0
    error_handling: float = 0.0
    unhandled_errors: int = 0
    overall_score: float = 0.0
    status: str = "failed"
    issues: list[str] = field(default_factory=list)
    scenarios: list[ScenarioResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the benchmark result."""
        return {
            "provider": self.provider,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "scenarios_total": self.scenarios_total,
            "scenarios_succeeded": self.scenarios_succeeded,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "max_latency_ms": round(self.max_latency_ms, 3),
            "fields_checked": self.fields_checked,
            "fields_matched": self.fields_matched,
            "normalization_quality": round(self.normalization_quality, 3),
            "jobs_produced": self.jobs_produced,
            "duplicate_jobs": self.duplicate_jobs,
            "duplicate_rate": round(self.duplicate_rate, 3),
            "error_cases_total": self.error_cases_total,
            "error_cases_handled": self.error_cases_handled,
            "error_handling": round(self.error_handling, 3),
            "unhandled_errors": self.unhandled_errors,
            "overall_score": round(self.overall_score, 1),
            "status": self.status,
            "issues": list(self.issues),
        }


class ConnectorValidator:
    """Validate provider connectors against mocked real-world scenarios.

    For every provider the validator measures success rate, response time,
    normalization quality, duplicate rate, and error handling without any
    network access. Connectors are rebuilt with a fake HTTP client so the
    benchmark is deterministic.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the validator with application settings."""
        self._settings = settings or Settings()

    def validate_connector(
        self,
        connector: BaseJobSourceConnector,
        source: JobSourceConfig | None = None,
    ) -> ConnectorBenchmarkResult:
        """Run the full scenario suite for a connector and return metrics.

        Connector metrics (success rate, quality, duplicates, error handling)
        are always measured against the well-formed scenario sources so the
        result reflects the connector implementation. When *source* is given it
        is used for report identity and its configuration is validated against
        the connector.
        """
        provider = connector.provider_name
        scenarios = _scenarios_for(provider)
        if not scenarios:
            issue = f"no validation scenarios for provider {provider}"
            return _failed_result(connector, source, issue)

        results: list[ScenarioResult] = []
        for scenario in scenarios:
            fake = _BenchmarkHttp(scenario.responder)
            test_connector = type(connector)(
                self._settings,
                http_client=fake,
                rate_limiter=RateLimiter(0.0),
            )
            results.append(self._run_scenario(test_connector, scenario))

        result = self._analyze(provider, source, scenarios, results)
        if source is not None:
            config_errors = connector.validate(source)
            if config_errors:
                result = replace(
                    result,
                    status="failed",
                    issues=[f"source config invalid: {'; '.join(config_errors)}", *result.issues],
                )
        return result

    def _run_scenario(
        self,
        connector: BaseJobSourceConnector,
        scenario: ConnectorScenario,
    ) -> ScenarioResult:
        """Execute one scenario and classify the outcome."""
        effective = scenario.source
        if scenario.expect_validate_errors:
            errors = connector.validate(effective)
            outcome = "handled" if errors else "unhandled"
            return ScenarioResult(
                name=scenario.name,
                kind="validate",
                outcome=outcome,
                latency_ms=0.0,
                jobs_count=0,
                error_type=None,
            )

        started = time.monotonic()
        try:
            jobs = connector.fetch(effective)
        except Exception as exc:
            latency = round((time.monotonic() - started) * 1000, 3)
            if isinstance(exc, DiscoveryError):
                outcome = "handled"
                expected = scenario.expected_error
                if expected is not None and not isinstance(exc, expected):
                    outcome = "mismatch"
                return ScenarioResult(
                    name=scenario.name,
                    kind="fetch",
                    outcome=outcome,
                    latency_ms=latency,
                    jobs_count=0,
                    error_type=type(exc).__name__,
                )
            return ScenarioResult(
                name=scenario.name,
                kind="fetch",
                outcome="unhandled",
                latency_ms=latency,
                jobs_count=0,
                error_type=type(exc).__name__,
            )
        latency = round((time.monotonic() - started) * 1000, 3)
        if scenario.expected_error is not None:
            return ScenarioResult(
                name=scenario.name,
                kind="fetch",
                outcome="unhandled",
                latency_ms=latency,
                jobs_count=len(jobs),
                error_type=None,
            )
        count_ok = scenario.expected_count is None or len(jobs) == scenario.expected_count
        outcome = "success" if count_ok else "mismatch"
        return ScenarioResult(
            name=scenario.name,
            kind="fetch",
            outcome=outcome,
            latency_ms=latency,
            jobs_count=len(jobs),
            error_type=None,
            jobs=tuple(jobs),
        )

    def _analyze(
        self,
        provider: str,
        source: JobSourceConfig | None,
        scenarios: list[ConnectorScenario],
        results: list[ScenarioResult],
    ) -> ConnectorBenchmarkResult:
        """Aggregate scenario outcomes into benchmark metrics."""
        nominal = [
            result
            for scenario, result in zip(scenarios, results, strict=True)
            if not scenario.expect_validate_errors and scenario.expected_error is None
        ]
        adversarial = [
            result
            for scenario, result in zip(scenarios, results, strict=True)
            if scenario.expect_validate_errors or scenario.expected_error is not None
        ]

        nominal_succeeded = sum(1 for r in nominal if r.outcome == "success")
        success_rate = nominal_succeeded / len(nominal) if nominal else 1.0

        error_handled = sum(1 for r in adversarial if r.outcome == "handled")
        error_handling = error_handled / len(adversarial) if adversarial else 1.0

        unhandled_errors = sum(1 for r in results if r.outcome == "unhandled")

        latencies = [r.latency_ms for r in results if r.kind == "fetch"]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        checked, matched, quality, jobs, duplicate_count, issues = self._score_normalization(
            scenarios, results
        )
        duplicate_rate = duplicate_count / len(jobs) if jobs else 0.0

        latency_score = min(1.0, _LATENCY_BUDGET_MS / (avg_latency + 1.0))
        overall_score = 100.0 * (
            0.25 * success_rate
            + 0.25 * quality
            + 0.20 * error_handling
            + 0.15 * (1.0 - duplicate_rate)
            + 0.15 * latency_score
        )

        if unhandled_errors:
            status = "failed"
        elif overall_score >= 80.0:
            status = "healthy"
        elif overall_score >= 50.0:
            status = "degraded"
        else:
            status = "failed"

        return ConnectorBenchmarkResult(
            provider=provider,
            source_id=source.id if source else None,
            source_name=source.name if source else None,
            source_type=source.type.value if source else None,
            scenarios_total=len(scenarios),
            scenarios_succeeded=nominal_succeeded + error_handled,
            success_rate=round(success_rate, 4),
            avg_latency_ms=round(avg_latency, 3),
            max_latency_ms=round(max_latency, 3),
            fields_checked=checked,
            fields_matched=matched,
            normalization_quality=round(quality, 4),
            jobs_produced=len(jobs),
            duplicate_jobs=duplicate_count,
            duplicate_rate=round(duplicate_rate, 4),
            error_cases_total=len(adversarial),
            error_cases_handled=error_handled,
            error_handling=round(error_handling, 4),
            unhandled_errors=unhandled_errors,
            overall_score=round(overall_score, 2),
            status=status,
            issues=issues,
            scenarios=results,
        )

    def _score_normalization(
        self,
        scenarios: list[ConnectorScenario],
        results: list[ScenarioResult],
    ) -> tuple[int, int, float, list[DiscoveredJob], int, list[str]]:
        """Score normalization quality and duplicate rate from the happy scenario."""
        issues: list[str] = []
        happy_result: ScenarioResult | None = None
        happy_expected: tuple[dict[str, Any], ...] | None = None
        for scenario, result in zip(scenarios, results, strict=True):
            if scenario.expected_fields is not None and result.outcome == "success":
                happy_result = result
                happy_expected = scenario.expected_fields
                break

        jobs: list[DiscoveredJob] = []
        for job in happy_result.jobs if happy_result else ():
            schema_fields = [attr for attr in NORMALIZED_JOB_SCHEMA if hasattr(job, attr)]
            if isinstance(job, DiscoveredJob) and len(schema_fields) == len(NORMALIZED_JOB_SCHEMA):
                jobs.append(job)
            else:
                issues.append(
                    f"job does not conform to the normalized schema: {type(job).__name__}"
                )

        if happy_result is None:
            issues.append(
                "no successful happy-path scenario; normalization quality could not be measured"
            )

        expected_by_key: dict[str, dict[str, Any]] = {}
        for entry in happy_expected or ():
            key = entry.get("external_id") or entry.get("url")
            if key is not None:
                expected_by_key[str(key)] = entry
        checked = 0
        matched = 0
        seen_urls: set[str] = set()
        duplicate_count = 0
        for job in jobs:
            url = job.url
            if url in seen_urls:
                duplicate_count += 1
            else:
                seen_urls.add(url)
            expected = expected_by_key.get(str(job.external_id))
            if expected is None:
                expected = expected_by_key.get(str(job.url))
            if expected is None:
                continue
            for field_name, expected_value in expected.items():
                if field_name in ("external_id", "url") or expected_value is None:
                    continue
                checked += 1
                actual = getattr(job, field_name, None)
                if actual is not None and str(actual) == str(expected_value):
                    matched += 1

        quality = matched / checked if checked else 0.0
        return checked, matched, quality, jobs, duplicate_count, issues


class _BenchmarkHttp:
    """HTTP test double that serves scenario payloads through a responder."""

    def __init__(self, responder: Callable[..., Any]) -> None:
        """Store the responder that produces payloads for every request."""
        self._responder = responder

    def get(self, url: str, *, headers=None, params=None, timeout=None) -> Any:  # noqa: ANN001, ANN401
        """Delegate a raw GET request to the responder."""
        return self._responder("get", url, headers=headers, params=params, timeout=timeout)

    def post(self, url: str, *, json=None, headers=None, timeout=None) -> Any:  # noqa: ANN001, ANN401
        """Delegate a raw POST request to the responder."""
        return self._responder("post", url, json=json, headers=headers, timeout=timeout)

    def get_json(self, url: str, *, headers=None, params=None) -> Any:  # noqa: ANN001, ANN401
        """Delegate a JSON GET request to the responder."""
        return self._responder("get_json", url, headers=headers, params=params)

    def post_json(self, url: str, *, json=None, headers=None) -> Any:  # noqa: ANN001, ANN401
        """Delegate a JSON POST request to the responder."""
        return self._responder("post_json", url, json=json, headers=headers)

    def get_text(self, url: str, *, headers=None, params=None) -> Any:  # noqa: ANN001, ANN401
        """Delegate a text GET request to the responder."""
        return self._responder("get_text", url, headers=headers, params=params)


def _source(
    source_type: JobSourceType,
    base_url: str,
    config: dict[str, Any] | None = None,
) -> JobSourceConfig:
    """Build a job source config used by a validation scenario."""
    return JobSourceConfig(
        id=0,
        name="Benchmark Source",
        type=source_type,
        base_url=base_url,
        config=config or {},
    )


def _boom() -> Any:  # noqa: ANN401
    """Raise when a responder that must never be called is invoked."""
    raise AssertionError("responder should not have been called for this scenario")


def _transport_error(_method: str, url: str, **_kwargs: Any) -> Any:  # noqa: ANN401
    """Simulate a transport-level failure for HTTP error scenarios."""
    raise SourceFetchError(f"simulated transport failure for {url}")


def _scenarios_for(provider: str) -> list[ConnectorScenario]:
    """Return the validation scenario suite for a provider."""
    return _PROVIDER_SCENARIOS.get(provider, [])


def _failed_result(
    connector: BaseJobSourceConnector | None,
    source: JobSourceConfig | None,
    issue: str,
) -> ConnectorBenchmarkResult:
    """Build a failed benchmark result for an unavailable connector."""
    provider = connector.provider_name if connector is not None else "unknown"
    return ConnectorBenchmarkResult(
        provider=provider,
        source_id=source.id if source else None,
        source_name=source.name if source else None,
        source_type=source.type.value if source else None,
        scenarios_total=0,
        success_rate=0.0,
        normalization_quality=0.0,
        duplicate_rate=0.0,
        error_handling=0.0,
        overall_score=0.0,
        status="failed",
        issues=[issue],
    )


def _rss_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the RSS/Atom connector."""
    source = _source(
        JobSourceType.RSS_FEED,
        "https://jobs.example.com/feed.xml",
        {"company": "Example", "default_location": "Remote"},
    )
    happy_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>Jobs</title>'
        "<item><guid>post-1</guid><title>Backend Engineer</title>"
        "<link>https://jobs.example.com/post-1</link>"
        "<description>Build APIs</description>"
        "<pubDate>Mon, 12 Jan 2026 10:00:00 GMT</pubDate></item>"
        "<item><guid>post-2</guid><title>Frontend Engineer</title>"
        "<link>https://jobs.example.com/post-2</link>"
        "<description>Build UI</description><pubDate>Tue, 13 Jan 2026 10:00:00 GMT</pubDate></item>"
        "</channel></rss>"
    )
    empty_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>Jobs</title></channel></rss>'
    )
    happy_expected = (
        {
            "external_id": "post-1",
            "url": "https://jobs.example.com/post-1",
            "title": "Backend Engineer",
            "company": "Example",
            "location": "Remote",
        },
        {
            "external_id": "post-2",
            "url": "https://jobs.example.com/post-2",
            "title": "Frontend Engineer",
            "company": "Example",
            "location": "Remote",
        },
    )
    return [
        ConnectorScenario(
            name="happy-rss",
            source=source,
            responder=lambda _method, _url, **_kwargs: happy_xml,
            expected_count=2,
            expected_fields=happy_expected,
        ),
        ConnectorScenario(
            name="empty-feed",
            source=source,
            responder=lambda _method, _url, **_kwargs: empty_xml,
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-xml",
            source=source,
            responder=lambda _method, _url, **_kwargs: "not xml at all",
            expected_error=SourceParseError,
        ),
        ConnectorScenario(
            name="transport-error",
            source=source,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
    ]


def _greenhouse_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the Greenhouse connector."""
    good = _source(
        JobSourceType.GREENHOUSE,
        "https://boards.greenhouse.io/acme",
        {"token": "acme", "company": "Acme"},
    )
    page_1 = {
        "jobs": [
            {
                "id": "101",
                "title": "Backend Engineer",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                "location": {"name": "Paris, France"},
                "departments": [{"name": "Engineering"}],
                "employment_type": {"name": "Full-time"},
                "remote": True,
                "content": "<p>Build APIs</p>",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
        "meta": {"page": 1, "total": 2, "per_page": 1},
    }
    page_2 = {
        "jobs": [
            {
                "id": "102",
                "title": "Data Analyst",
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
                "location": "Remote",
                "departments": [{"name": "Data"}],
                "employment_type": "Part-time",
                "remote": False,
                "content": "<p>Analyze data</p>",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        ],
        "meta": {"page": 2, "total": 2, "per_page": 1},
    }

    def _happy(_method: str, _url: str, **kwargs: Any) -> Any:  # noqa: ANN401
        """Serve Greenhouse pages based on the requested page number."""
        page = (kwargs.get("params") or {}).get("page")
        return page_1 if page == 1 else page_2

    missing = _source(JobSourceType.GREENHOUSE, "https://boards.greenhouse.io", {})
    return [
        ConnectorScenario(
            name="happy-paginated",
            source=good,
            responder=_happy,
            expected_count=2,
            expected_fields=(
                {
                    "external_id": "101",
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "location": "Paris, France",
                    "department": "Engineering",
                    "employment_type": "Full-time",
                    "remote_status": "remote",
                },
                {
                    "external_id": "102",
                    "title": "Data Analyst",
                    "company": "Acme",
                    "location": "Remote",
                    "department": "Data",
                    "employment_type": "Part-time",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-board",
            source=good,
            responder=lambda _m, _u, **_kwargs: {
                "jobs": [],
                "meta": {"page": 1, "total": 0, "per_page": 10},
            },
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=good,
            responder=lambda _m, _u, **_kwargs: {"unexpected": True},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=good,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
        ConnectorScenario(
            name="missing-config-fetch",
            source=missing,
            responder=_boom,
            expected_error=SourceConfigError,
        ),
        ConnectorScenario(
            name="missing-config-validate",
            source=missing,
            responder=_boom,
            expect_validate_errors=True,
        ),
    ]


def _lever_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the Lever connector."""
    good = _source(
        JobSourceType.LEVER,
        "https://jobs.lever.co/acme",
        {"company": "acme"},
    )
    payload = [
        {
            "id": "abc",
            "text": "Frontend Engineer",
            "hostedUrl": "https://jobs.lever.co/acme/abc",
            "categories": {
                "location": "Remote",
                "team": "Engineering",
                "commitment": "Full-time",
            },
            "descriptionPlain": "Build UI with React. Remote friendly.",
            "lists": [{"title": "Requirements", "content": "3+ years React"}],
            "createdAt": 1735689600000,
        }
    ]
    missing = _source(JobSourceType.LEVER, "https://jobs.lever.co", {})
    return [
        ConnectorScenario(
            name="happy-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: payload,
            expected_count=1,
            expected_fields=(
                {
                    "external_id": "abc",
                    "title": "Frontend Engineer",
                    "company": "acme",
                    "location": "Remote",
                    "department": "Engineering",
                    "employment_type": "Full-time",
                    "remote_status": "remote",
                    "requirements": "3+ years React",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: [],
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=good,
            responder=lambda _m, _u, **_kwargs: {"not": "a list"},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=good,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
        ConnectorScenario(
            name="missing-config-fetch",
            source=missing,
            responder=_boom,
            expected_error=SourceConfigError,
        ),
        ConnectorScenario(
            name="missing-config-validate",
            source=missing,
            responder=_boom,
            expect_validate_errors=True,
        ),
    ]


def _ashby_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the Ashby connector."""
    good = _source(
        JobSourceType.ASHBY,
        "https://jobs.ashbyhq.com/acme",
        {"board": "acme"},
    )
    page_1 = {
        "jobs": [{"id": "1", "title": "Engineer", "jobUrl": "https://x/1"}],
        "hasMore": True,
        "nextCursor": "cur",
    }
    page_2 = {
        "jobs": [{"id": "2", "title": "Designer", "jobUrl": "https://x/2"}],
        "hasMore": False,
        "nextCursor": None,
    }

    def _happy(_method: str, _url: str, **kwargs: Any) -> Any:  # noqa: ANN401
        """Serve Ashby pages based on the posted pagination cursor."""
        body = kwargs.get("json") or {}
        return page_2 if body.get("paginationCursor") else page_1

    missing = _source(JobSourceType.ASHBY, "https://jobs.ashbyhq.com", {})
    return [
        ConnectorScenario(
            name="happy-paginated",
            source=good,
            responder=_happy,
            expected_count=2,
            expected_fields=(
                {"external_id": "1", "title": "Engineer", "url": "https://x/1", "company": "acme"},
                {"external_id": "2", "title": "Designer", "url": "https://x/2", "company": "acme"},
            ),
        ),
        ConnectorScenario(
            name="empty-board",
            source=good,
            responder=lambda _m, _u, **_kwargs: {"jobs": [], "hasMore": False, "nextCursor": None},
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=good,
            responder=lambda _m, _u, **_kwargs: {},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=good,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
        ConnectorScenario(
            name="missing-config-fetch",
            source=missing,
            responder=_boom,
            expected_error=SourceConfigError,
        ),
        ConnectorScenario(
            name="missing-config-validate",
            source=missing,
            responder=_boom,
            expect_validate_errors=True,
        ),
    ]


def _smart_recruiters_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the SmartRecruiters connector."""
    good = _source(
        JobSourceType.SMART_RECRUITERS,
        "https://jobs.smartrecruiters.com/Acme",
        {"company": "Acme"},
    )
    payload = {
        "content": [
            {
                "id": "r1",
                "name": "Data Scientist",
                "ref": "https://jobs.smartrecruiters.com/Acme/r1",
                "location": {"city": "Lyon", "country": "France"},
                "department": {"label": "Data"},
                "releasedDate": "2026-02-01T00:00:00Z",
                "jobAd": {
                    "sections": [
                        {"title": "description", "jobDescription": "<p>Analyze data</p>"},
                        {"title": "requirements", "jobDescription": "<p>Python</p>"},
                    ]
                },
            }
        ],
        "totalFound": 1,
    }
    missing = _source(JobSourceType.SMART_RECRUITERS, "https://jobs.smartrecruiters.com", {})
    return [
        ConnectorScenario(
            name="happy-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: payload,
            expected_count=1,
            expected_fields=(
                {
                    "external_id": "r1",
                    "title": "Data Scientist",
                    "company": "Acme",
                    "location": "Lyon, France",
                    "department": "Data",
                    "requirements": "Python",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: {"content": [], "totalFound": 0},
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=good,
            responder=lambda _m, _u, **_kwargs: {},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=good,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
        ConnectorScenario(
            name="missing-config-fetch",
            source=missing,
            responder=_boom,
            expected_error=SourceConfigError,
        ),
        ConnectorScenario(
            name="missing-config-validate",
            source=missing,
            responder=_boom,
            expect_validate_errors=True,
        ),
    ]


def _teamtailor_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the Teamtailor connector."""
    good = _source(
        JobSourceType.TEAMTAILOR,
        "https://careers.example.com",
        {"api_key": "secret", "company": "Example"},
    )
    payload = {
        "data": [
            {
                "id": "tt-1",
                "attributes": {
                    "title": "DevOps Engineer",
                    "url": "https://careers.teamtailor.com/jobs/tt-1",
                    "body": "Run infrastructure",
                    "remote": True,
                },
                "relationships": {
                    "department": {"data": {"id": "d1", "type": "departments"}},
                    "location": {"data": {"id": "l1", "type": "locations"}},
                },
            }
        ],
        "included": [
            {"id": "d1", "type": "departments", "attributes": {"name": "Platform"}},
            {
                "id": "l1",
                "type": "locations",
                "attributes": {"city": "Berlin", "country": "Germany"},
            },
        ],
        "meta": {"pagination": {"current-page": 1, "last-page": 1}},
    }
    missing = _source(JobSourceType.TEAMTAILOR, "https://careers.example.com", {})
    return [
        ConnectorScenario(
            name="happy-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: payload,
            expected_count=1,
            expected_fields=(
                {
                    "external_id": "tt-1",
                    "title": "DevOps Engineer",
                    "company": "Example",
                    "location": "Berlin, Germany",
                    "department": "Platform",
                    "remote_status": "remote",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: {
                "data": [],
                "included": [],
                "meta": {"pagination": {"current-page": 1, "last-page": 1}},
            },
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=good,
            responder=lambda _m, _u, **_kwargs: {},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=good,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
        ConnectorScenario(
            name="missing-config-validate",
            source=missing,
            responder=_boom,
            expect_validate_errors=True,
        ),
    ]


def _wttj_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the Welcome to the Jungle connector."""
    good = _source(
        JobSourceType.WELCOME_TO_THE_JUNGLE,
        "https://www.welcometothejungle.com/fr/companies/acme",
        {"slug": "acme", "company": "Acme"},
    )
    payload = {
        "data": [
            {
                "id": "slug-1",
                "title": "Product Designer",
                "url": "https://www.welcometothejungle.com/fr/companies/acme/jobs/slug-1",
                "location": {"city": "Paris", "country": "France"},
                "contract_type": {"text": "CDI"},
                "description": "Design great products",
                "published_at": "2026-03-01T00:00:00Z",
            }
        ]
    }
    missing = _source(JobSourceType.WELCOME_TO_THE_JUNGLE, "https://www.welcometothejungle.com", {})
    return [
        ConnectorScenario(
            name="happy-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: payload,
            expected_count=1,
            expected_fields=(
                {
                    "external_id": "slug-1",
                    "title": "Product Designer",
                    "company": "Acme",
                    "location": "Paris, France",
                    "employment_type": "CDI",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-postings",
            source=good,
            responder=lambda _m, _u, **_kwargs: {"data": []},
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=good,
            responder=lambda _m, _u, **_kwargs: {},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=good,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
        ConnectorScenario(
            name="missing-config-fetch",
            source=missing,
            responder=_boom,
            expected_error=SourceConfigError,
        ),
        ConnectorScenario(
            name="missing-config-validate",
            source=missing,
            responder=_boom,
            expect_validate_errors=True,
        ),
    ]


def _remote_ok_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the RemoteOK connector."""
    source = _source(JobSourceType.REMOTE_OK, "https://remoteok.com")
    payload = [
        {"location": "all"},
        {
            "id": 42,
            "position": "Python Developer",
            "company": "Remote Co",
            "url": "https://remoteok.com/remote-jobs/python-dev",
            "location": "Worldwide",
            "description": "<p>Build tools</p>",
            "tags": ["python", "aws"],
            "date": 1735689600,
        },
        {
            "id": 43,
            "position": "DevOps Engineer",
            "company": "Remote Co",
            "url": "https://remoteok.com/remote-jobs/devops",
            "location": "Worldwide",
            "description": "<p>Run infra</p>",
            "tags": ["docker", "k8s"],
            "date": 1735776000,
        },
    ]
    return [
        ConnectorScenario(
            name="happy-feed",
            source=source,
            responder=lambda _m, _u, **_kwargs: payload,
            expected_count=2,
            expected_fields=(
                {
                    "external_id": "42",
                    "title": "Python Developer",
                    "company": "Remote Co",
                    "location": "Worldwide",
                    "remote_status": "remote",
                    "requirements": "python, aws",
                },
                {
                    "external_id": "43",
                    "title": "DevOps Engineer",
                    "company": "Remote Co",
                    "location": "Worldwide",
                    "remote_status": "remote",
                    "requirements": "docker, k8s",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-feed",
            source=source,
            responder=lambda _m, _u, **_kwargs: [],
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=source,
            responder=lambda _m, _u, **_kwargs: {"not": "a list"},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=source,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
    ]


def _wellfound_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the Wellfound connector."""
    source = _source(
        JobSourceType.WELLFOUND,
        "https://wellfound.com/company/startup",
        {"company": "Startup Inc"},
    )
    payload = {
        "jobs": [
            {
                "id": 7,
                "title": "Growth Marketer",
                "company": {"name": "Startup Inc"},
                "location": {"display_name": "Remote"},
                "urls": {"apply_url": "https://wellfound.com/jobs/7"},
                "description": "<p>Marketing</p>",
                "created_at": "2026-04-01T00:00:00Z",
            },
            {
                "id": 8,
                "title": "Sales Rep",
                "company": {"name": "Startup Inc"},
                "location": {"display_name": "New York, NY"},
                "urls": {"apply_url": "https://wellfound.com/jobs/8"},
                "description": "<p>Sales</p>",
                "created_at": "2026-04-02T00:00:00Z",
            },
        ],
        "total": 2,
    }
    return [
        ConnectorScenario(
            name="happy-jobs",
            source=source,
            responder=lambda _m, _u, **_kwargs: payload,
            expected_count=2,
            expected_fields=(
                {
                    "external_id": "7",
                    "title": "Growth Marketer",
                    "company": "Startup Inc",
                    "location": "Remote",
                },
                {
                    "external_id": "8",
                    "title": "Sales Rep",
                    "company": "Startup Inc",
                    "location": "New York, NY",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-jobs",
            source=source,
            responder=lambda _m, _u, **_kwargs: {"jobs": [], "total": 0},
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-payload",
            source=source,
            responder=lambda _m, _u, **_kwargs: {},
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=source,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
    ]


def _company_pages_scenarios() -> list[ConnectorScenario]:
    """Return the validation scenarios for the company career pages connector."""
    good = _source(
        JobSourceType.COMPANY_PAGES,
        "https://acme.com/careers",
        {"company": "Acme", "job_links_selector": "a.job", "scrape_details": False},
    )
    list_html = (
        '<html><body><a class="job" href="/jobs/1">Job One</a>'
        '<a class="job" href="/jobs/2">Job Two</a></body></html>'
    )
    missing = _source(JobSourceType.COMPANY_PAGES, "https://acme.com/careers", {})
    return [
        ConnectorScenario(
            name="happy-listing",
            source=good,
            responder=lambda _m, _u, **_kwargs: list_html,
            expected_count=2,
            expected_fields=(
                {
                    "url": "https://acme.com/jobs/1",
                    "title": "Job One",
                    "company": "Acme",
                },
                {
                    "url": "https://acme.com/jobs/2",
                    "title": "Job Two",
                    "company": "Acme",
                },
            ),
        ),
        ConnectorScenario(
            name="empty-listing",
            source=good,
            responder=lambda _m, _u, **_kwargs: "<html><body></body></html>",
            expected_count=0,
        ),
        ConnectorScenario(
            name="malformed-markup",
            source=good,
            responder=lambda _m, _u, **_kwargs: "",
            expected_count=0,
        ),
        ConnectorScenario(
            name="transport-error",
            source=good,
            responder=_transport_error,
            expected_error=SourceFetchError,
        ),
        ConnectorScenario(
            name="missing-config-validate",
            source=missing,
            responder=_boom,
            expect_validate_errors=True,
        ),
    ]


_PROVIDER_SCENARIOS: dict[str, list[ConnectorScenario]] = {
    "rss": _rss_scenarios(),
    "greenhouse": _greenhouse_scenarios(),
    "lever": _lever_scenarios(),
    "ashby": _ashby_scenarios(),
    "smart_recruiters": _smart_recruiters_scenarios(),
    "teamtailor": _teamtailor_scenarios(),
    "welcome_to_the_jungle": _wttj_scenarios(),
    "remote_ok": _remote_ok_scenarios(),
    "wellfound": _wellfound_scenarios(),
    "company_pages": _company_pages_scenarios(),
}
