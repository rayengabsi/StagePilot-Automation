from __future__ import annotations

from dataclasses import dataclass


class RecommendationError(Exception):
    """Base error for recommendation operations."""


class ProfileNotReadyError(RecommendationError):
    """No master profile exists yet for matching."""


@dataclass(frozen=True, slots=True)
class ValidationError:
    field: str
    message: str
    value: str | None = None


class RecommendationValidationError(RecommendationError):
    def __init__(self, errors: list[ValidationError]) -> None:
        self.errors = errors
        super().__init__(f"Recommendation validation failed with {len(errors)} error(s)")

    def to_dict(self) -> list[dict[str, str | None]]:
        return [{"field": e.field, "message": e.message, "value": e.value} for e in self.errors]
