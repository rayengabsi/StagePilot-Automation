from __future__ import annotations


class ApplicationError(Exception):
    """Base error for the application execution engine."""


class ApplicationNotFoundError(ApplicationError):
    """Job application not found."""


class DuplicateApplicationError(ApplicationError):
    """An open application already exists for the recommendation."""


class InvalidStateTransitionError(ApplicationError):
    """Attempted an invalid application state transition."""


class ReminderError(ApplicationError):
    """Follow-up reminder operation failed."""


class OutcomeError(ApplicationError):
    """Outcome tracking operation failed."""
