from __future__ import annotations

from dataclasses import dataclass


class MasterProfileError(Exception):
    """Base error for master profile operations."""


class ProfileNotFoundError(MasterProfileError):
    """No profile exists yet."""


class ProfileImportError(MasterProfileError):
    """Failed to import or parse a resume file."""


@dataclass(frozen=True, slots=True)
class ValidationError:
    """One structured validation issue for a profile field."""

    field: str
    message: str
    value: str | None = None


class ProfileValidationError(MasterProfileError):
    """One or more validation errors occurred during profile processing."""

    def __init__(self, errors: list[ValidationError]) -> None:
        self.errors = errors
        super().__init__(f"Profile validation failed with {len(errors)} error(s)")

    def to_dict(self) -> list[dict[str, str | None]]:
        return [{"field": e.field, "message": e.message, "value": e.value} for e in self.errors]
