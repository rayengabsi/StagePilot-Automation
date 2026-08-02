from __future__ import annotations

from enum import StrEnum


class ApplicationState(StrEnum):
    """Lifecycle state of a job application."""

    DRAFT = "draft"
    READY = "ready"
    SUBMITTED = "submitted"
    VIEWED = "viewed"
    INTERVIEW = "interview"
    ASSESSMENT = "assessment"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"


VALID_TRANSITIONS: dict[ApplicationState, set[ApplicationState]] = {
    ApplicationState.DRAFT: {
        ApplicationState.READY,
        ApplicationState.SUBMITTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.ARCHIVED,
    },
    ApplicationState.READY: {
        ApplicationState.SUBMITTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.ARCHIVED,
    },
    ApplicationState.SUBMITTED: {
        ApplicationState.VIEWED,
        ApplicationState.INTERVIEW,
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.ARCHIVED,
    },
    ApplicationState.VIEWED: {
        ApplicationState.INTERVIEW,
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.ARCHIVED,
    },
    ApplicationState.INTERVIEW: {
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.ARCHIVED,
    },
    ApplicationState.ASSESSMENT: {
        ApplicationState.INTERVIEW,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
        ApplicationState.WITHDRAWN,
        ApplicationState.ARCHIVED,
    },
    ApplicationState.OFFER: {
        ApplicationState.ARCHIVED,
        ApplicationState.WITHDRAWN,
    },
    ApplicationState.REJECTED: {ApplicationState.ARCHIVED},
    ApplicationState.WITHDRAWN: {ApplicationState.ARCHIVED},
    ApplicationState.ARCHIVED: set(),
}


def is_valid_transition(from_state: ApplicationState, to_state: ApplicationState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())


class ApplicationAction(StrEnum):
    """Actions recorded in the application audit history."""

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    ARCHIVED = "archived"
    NOTE_ADDED = "note_added"
    LABEL_ADDED = "label_added"
    LABEL_REMOVED = "label_removed"
    REMINDER_SCHEDULED = "reminder_scheduled"
    REMINDER_COMPLETED = "reminder_completed"
    REMINDER_SNOOZED = "reminder_snoozed"
    REMINDER_CANCELLED = "reminder_cancelled"
    OUTCOME_RECORDED = "outcome_recorded"


class FollowUpStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    SNOOZED = "snoozed"
    CANCELLED = "cancelled"


class OutcomeType(StrEnum):
    """Final outcome tracked for an application."""

    HIRED = "hired"
    OFFER_DECLINED = "offer_declined"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    OTHER = "other"
