from __future__ import annotations


class ApprovalError(Exception):
    """Base error for the approval system."""


class InvalidTransitionError(ApprovalError):
    """Attempted an invalid state transition."""


class PackageNotFoundError(ApprovalError):
    """Application package not found."""


class QueueFullError(ApprovalError):
    """Approval queue is full."""


class DuplicateApprovalError(ApprovalError):
    """Package has already been approved."""


class UnauthorizedError(ApprovalError):
    """User is not authorized to perform this action."""


class DocumentNotFoundError(ApprovalError):
    """Required document is missing from the package."""


class SnapshotError(ApprovalError):
    """Snapshot creation or verification failed."""


class TelegramError(ApprovalError):
    """Telegram communication failed."""


class RollbackError(ApprovalError):
    """Database rollback failed."""
