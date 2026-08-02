from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class JobClassification:
    """Structured intelligence derived from a normalized job listing.

    Every field is ``None`` when the underlying signals are insufficient or
    contradictory. Original connector-extracted values (``department``,
    ``employment_type``, ``remote_status``) are preserved separately; this
    entity stores the normalized classification only.
    """

    specialization: str | None = None
    seniority: str | None = None
    employment_type: str | None = None
    work_mode: str | None = None
    urgency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the classification."""
        return {
            "specialization": self.specialization,
            "seniority": self.seniority,
            "employment_type": self.employment_type,
            "work_mode": self.work_mode,
            "urgency": self.urgency,
        }
