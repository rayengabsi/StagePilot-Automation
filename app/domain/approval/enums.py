from __future__ import annotations

from enum import StrEnum


class ApprovalState(StrEnum):
    NEW = "new"
    QUEUED = "queued"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    SKIPPED = "skipped"
    ARCHIVED = "archived"


VALID_TRANSITIONS: dict[ApprovalState, set[ApprovalState]] = {
    ApprovalState.NEW: {ApprovalState.QUEUED, ApprovalState.ARCHIVED},
    ApprovalState.QUEUED: {
        ApprovalState.UNDER_REVIEW,
        ApprovalState.ARCHIVED,
        ApprovalState.SKIPPED,
    },
    ApprovalState.UNDER_REVIEW: {
        ApprovalState.APPROVED,
        ApprovalState.REJECTED,
        ApprovalState.REVISION_REQUESTED,
        ApprovalState.SKIPPED,
        ApprovalState.ARCHIVED,
    },
    ApprovalState.APPROVED: {ApprovalState.ARCHIVED},
    ApprovalState.REJECTED: {ApprovalState.ARCHIVED, ApprovalState.QUEUED},
    ApprovalState.REVISION_REQUESTED: {ApprovalState.QUEUED, ApprovalState.ARCHIVED},
    ApprovalState.SKIPPED: {ApprovalState.ARCHIVED, ApprovalState.QUEUED},
    ApprovalState.ARCHIVED: set(),
}


def is_valid_transition(from_state: ApprovalState, to_state: ApprovalState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())


class ApprovalAction(StrEnum):
    QUEUED = "queued"
    VIEWED = "viewed"
    OPENED_RESUME = "opened_resume"
    OPENED_COVER_LETTER = "opened_cover_letter"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    REVISION_REQUESTED = "revision_requested"
    ARCHIVED = "archived"


class QueueStrategy(StrEnum):
    FIFO = "fifo"
    HIGHEST_SCORE = "highest_score"
    DEADLINE_PRIORITY = "deadline_priority"
    NEWEST_FIRST = "newest_first"
    OLDEST_FIRST = "oldest_first"
