from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.matching.enums import DuplicateStrategy, RejectionCategory


@dataclass(frozen=True, slots=True)
class RejectionReason:
    """One structured reason why a job was rejected by a hard filter."""

    category: RejectionCategory
    detail: str
    matched_keyword: str | None = None


@dataclass(frozen=True, slots=True)
class FilterResult:
    """Result of applying hard filters to a single job."""

    passed: bool
    rejection_reasons: tuple[RejectionReason, ...] = ()


@dataclass(frozen=True, slots=True)
class DuplicateResult:
    """Result of checking whether a job is a duplicate of an existing one."""

    is_duplicate: bool
    strategy: DuplicateStrategy | None = None
    existing_job_id: int | None = None
    confidence: float | None = None
    matched_value: str | None = None


@dataclass(slots=True)
class JobMatchMetrics:
    """Aggregated metrics for one discovery run."""

    total_discovered: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    inserted: int = 0
    updated: int = 0
    rejection_breakdown: dict[str, int] = field(default_factory=dict)
    duplicate_strategy_breakdown: dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0.0
    run_id: str = ""
    sources_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary of metrics."""
        return {
            "total_discovered": self.total_discovered,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "duplicates": self.duplicates,
            "inserted": self.inserted,
            "updated": self.updated,
            "rejection_breakdown": dict(self.rejection_breakdown),
            "duplicate_strategy_breakdown": dict(self.duplicate_strategy_breakdown),
            "duration_seconds": round(self.duration_seconds, 3),
            "run_id": self.run_id,
            "sources_count": self.sources_count,
        }
