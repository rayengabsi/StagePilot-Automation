from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.applications.enums import (
    ApplicationAction,
    ApplicationState,
    FollowUpStatus,
    OutcomeType,
)


@dataclass(frozen=True, slots=True)
class JobApplication:
    """A tracked job application linked to its originating recommendation."""

    recommendation_id: int
    job_id: int
    profile_id: int
    profile_version: str
    company_name: str
    job_title: str

    status: ApplicationState = ApplicationState.DRAFT
    application_package_id: int | None = None
    resume_path: str = ""
    cover_letter_path: str = ""
    labels: tuple[str, ...] = ()

    submitted_at: str | None = None
    responded_at: str | None = None
    offer_at: str | None = None
    archived_at: str | None = None

    id: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "recommendation_id": self.recommendation_id,
            "job_id": self.job_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "company_name": self.company_name,
            "job_title": self.job_title,
            "status": self.status.value,
            "application_package_id": self.application_package_id,
            "resume_path": self.resume_path,
            "cover_letter_path": self.cover_letter_path,
            "labels": list(self.labels),
            "submitted_at": self.submitted_at,
            "responded_at": self.responded_at,
            "offer_at": self.offer_at,
            "archived_at": self.archived_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class ApplicationEvent:
    """Audit record of a single application mutation."""

    application_id: int
    action: ApplicationAction
    actor: str
    comment: str = ""
    previous_state: ApplicationState | None = None
    new_state: ApplicationState | None = None

    id: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "action": self.action.value,
            "actor": self.actor,
            "comment": self.comment,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "new_state": self.new_state.value if self.new_state else None,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ApplicationNote:
    application_id: int
    author: str
    text: str
    id: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "author": self.author,
            "text": self.text,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ApplicationTimelineEvent:
    """A human-facing timeline entry for an application."""

    application_id: int
    event_type: str
    title: str
    description: str = ""
    occurred_at: str = ""
    id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "event_type": self.event_type,
            "title": self.title,
            "description": self.description,
            "occurred_at": self.occurred_at,
        }


@dataclass(frozen=True, slots=True)
class FollowUpReminder:
    """A configurable follow-up reminder for an application."""

    application_id: int
    due_at: str
    message: str
    status: FollowUpStatus = FollowUpStatus.PENDING
    completed_at: str | None = None
    id: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "due_at": self.due_at,
            "message": self.message,
            "status": self.status.value,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ApplicationOutcome:
    """Final outcome recorded for an application."""

    application_id: int
    outcome_type: OutcomeType
    notes: str = ""
    recorded_at: str = ""
    id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "application_id": self.application_id,
            "outcome_type": self.outcome_type.value,
            "notes": self.notes,
            "recorded_at": self.recorded_at,
        }
