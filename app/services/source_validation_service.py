from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.config.settings import Settings, get_settings
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.errors import ConnectorNotFoundError
from app.infrastructure.job_sources.registry import (
    ConnectorRegistry,
    build_connector_registry,
)
from app.infrastructure.job_sources.validation import (
    ConnectorBenchmarkResult,
    ConnectorValidator,
)
from app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class SourceBenchmarkEntry:
    """Health report entry for one configured source."""

    source_id: int | None
    source_name: str | None
    provider: str
    source_type: str | None
    scenarios_total: int
    success_rate: float
    avg_latency_ms: float
    normalization_quality: float
    duplicate_rate: float
    error_handling: float
    overall_score: float
    status: str
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the entry."""
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "provider": self.provider,
            "source_type": self.source_type,
            "scenarios_total": self.scenarios_total,
            "success_rate": round(self.success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "normalization_quality": round(self.normalization_quality, 3),
            "duplicate_rate": round(self.duplicate_rate, 3),
            "error_handling": round(self.error_handling, 3),
            "overall_score": round(self.overall_score, 1),
            "status": self.status,
            "issues": list(self.issues),
        }

    @classmethod
    def from_result(cls, result: ConnectorBenchmarkResult) -> SourceBenchmarkEntry:
        """Build a report entry from a connector benchmark result."""
        return cls(
            source_id=result.source_id,
            source_name=result.source_name,
            provider=result.provider,
            source_type=result.source_type,
            scenarios_total=result.scenarios_total,
            success_rate=result.success_rate,
            avg_latency_ms=result.avg_latency_ms,
            normalization_quality=result.normalization_quality,
            duplicate_rate=result.duplicate_rate,
            error_handling=result.error_handling,
            overall_score=result.overall_score,
            status=result.status,
            issues=list(result.issues),
        )


@dataclass(frozen=True, slots=True)
class ProviderBenchmarkSummary:
    """Aggregated health metrics for one provider across sources."""

    provider: str
    source_count: int
    avg_success_rate: float
    avg_latency_ms: float
    avg_normalization_quality: float
    avg_duplicate_rate: float
    avg_error_handling: float
    avg_score: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the summary."""
        return {
            "provider": self.provider,
            "source_count": self.source_count,
            "avg_success_rate": round(self.avg_success_rate, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "avg_normalization_quality": round(self.avg_normalization_quality, 3),
            "avg_duplicate_rate": round(self.avg_duplicate_rate, 3),
            "avg_error_handling": round(self.avg_error_handling, 3),
            "avg_score": round(self.avg_score, 1),
            "status": self.status,
        }

    @classmethod
    def aggregate(
        cls,
        provider: str,
        entries: list[SourceBenchmarkEntry],
    ) -> ProviderBenchmarkSummary:
        """Aggregate benchmark entries for a provider into one summary."""
        count = len(entries)
        if count == 0:
            return cls(
                provider=provider,
                source_count=0,
                avg_success_rate=0.0,
                avg_latency_ms=0.0,
                avg_normalization_quality=0.0,
                avg_duplicate_rate=0.0,
                avg_error_handling=0.0,
                avg_score=0.0,
                status="unknown",
            )
        statuses = [entry.status for entry in entries]
        if "failed" in statuses:
            status = "failed"
        elif "degraded" in statuses:
            status = "degraded"
        else:
            status = "healthy"
        return cls(
            provider=provider,
            source_count=count,
            avg_success_rate=sum(e.success_rate for e in entries) / count,
            avg_latency_ms=sum(e.avg_latency_ms for e in entries) / count,
            avg_normalization_quality=sum(e.normalization_quality for e in entries) / count,
            avg_duplicate_rate=sum(e.duplicate_rate for e in entries) / count,
            avg_error_handling=sum(e.error_handling for e in entries) / count,
            avg_score=sum(e.overall_score for e in entries) / count,
            status=status,
        )


@dataclass(frozen=True, slots=True)
class SourcesHealthReport:
    """Health report for all configured sources and their providers."""

    generated_at: datetime
    overall_score: float
    overall_status: str
    sources_count: int
    healthy_count: int
    degraded_count: int
    failed_count: int
    sources: list[SourceBenchmarkEntry]
    providers: list[ProviderBenchmarkSummary]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the report."""
        return {
            "generated_at": self.generated_at,
            "overall_score": round(self.overall_score, 1),
            "overall_status": self.overall_status,
            "sources_count": self.sources_count,
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "failed_count": self.failed_count,
            "providers": [summary.to_dict() for summary in self.providers],
            "sources": [entry.to_dict() for entry in self.sources],
        }

    @classmethod
    def from_entries(
        cls,
        entries: list[SourceBenchmarkEntry],
        generated_at: datetime | None = None,
    ) -> SourcesHealthReport:
        """Aggregate benchmark entries into a health report."""
        generated_at = generated_at or utc_now()
        healthy_count = sum(1 for entry in entries if entry.status == "healthy")
        degraded_count = sum(1 for entry in entries if entry.status == "degraded")
        failed_count = sum(1 for entry in entries if entry.status == "failed")
        score = sum(entry.overall_score for entry in entries) / len(entries) if entries else 0.0
        if failed_count:
            status = "failed"
        elif degraded_count:
            status = "degraded"
        elif entries:
            status = "healthy"
        else:
            status = "unknown"
        providers: dict[str, list[SourceBenchmarkEntry]] = {}
        for entry in entries:
            providers.setdefault(entry.provider, []).append(entry)
        summaries = [ProviderBenchmarkSummary.aggregate(p, group) for p, group in providers.items()]
        return cls(
            generated_at=generated_at,
            overall_score=round(score, 2),
            overall_status=status,
            sources_count=len(entries),
            healthy_count=healthy_count,
            degraded_count=degraded_count,
            failed_count=failed_count,
            sources=list(entries),
            providers=summaries,
        )


class SourceValidationService:
    """Run the connector validation benchmark across configured sources."""

    def __init__(
        self,
        settings: Settings | None = None,
        registry: ConnectorRegistry | None = None,
        validator: ConnectorValidator | None = None,
    ) -> None:
        """Initialize the validation service with its dependencies."""
        self._settings = settings or get_settings()
        self._registry = registry or build_connector_registry(self._settings)
        self._validator = validator or ConnectorValidator(self._settings)

    def benchmark_sources(
        self,
        source_configs: list[JobSourceConfig],
        generated_at: datetime | None = None,
    ) -> SourcesHealthReport:
        """Benchmark every configured source and return a health report.

        When no sources are configured every enabled provider in the registry is
        benchmarked so the report always covers the full provider set.
        """
        if source_configs:
            entries = self._benchmark_source_configs(source_configs)
        else:
            entries = self._benchmark_all_providers()
        return SourcesHealthReport.from_entries(entries, generated_at=generated_at)

    def _benchmark_source_configs(
        self,
        source_configs: list[JobSourceConfig],
    ) -> list[SourceBenchmarkEntry]:
        """Benchmark each configured source using its registered connector."""
        entries: list[SourceBenchmarkEntry] = []
        for source in source_configs:
            try:
                connector = self._registry.get(source.type)
            except ConnectorNotFoundError as exc:
                result = ConnectorBenchmarkResult(
                    provider=source.type.value,
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.type.value,
                    overall_score=0.0,
                    status="failed",
                    issues=[str(exc)],
                )
                entries.append(SourceBenchmarkEntry.from_result(result))
                continue
            entries.append(
                SourceBenchmarkEntry.from_result(
                    self._validator.validate_connector(connector, source)
                )
            )
        return entries

    def _benchmark_all_providers(self) -> list[SourceBenchmarkEntry]:
        """Benchmark every provider registered in the registry without a source."""
        return [
            SourceBenchmarkEntry.from_result(self._validator.validate_connector(connector))
            for connector in self._registry.all()
        ]
