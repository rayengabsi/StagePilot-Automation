from __future__ import annotations

import pytest
from app.domain.applications import (
    ApplicationAction,
    ApplicationEvent,
    ApplicationNote,
    ApplicationOutcome,
    ApplicationState,
    ApplicationTimelineEvent,
    FollowUpReminder,
    FollowUpStatus,
    JobApplication,
    OutcomeType,
    is_valid_transition,
)


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (ApplicationState.DRAFT, ApplicationState.READY),
        (ApplicationState.DRAFT, ApplicationState.SUBMITTED),
        (ApplicationState.READY, ApplicationState.SUBMITTED),
        (ApplicationState.READY, ApplicationState.WITHDRAWN),
        (ApplicationState.SUBMITTED, ApplicationState.VIEWED),
        (ApplicationState.SUBMITTED, ApplicationState.INTERVIEW),
        (ApplicationState.SUBMITTED, ApplicationState.OFFER),
        (ApplicationState.SUBMITTED, ApplicationState.REJECTED),
        (ApplicationState.VIEWED, ApplicationState.INTERVIEW),
        (ApplicationState.VIEWED, ApplicationState.ASSESSMENT),
        (ApplicationState.INTERVIEW, ApplicationState.ASSESSMENT),
        (ApplicationState.ASSESSMENT, ApplicationState.INTERVIEW),
        (ApplicationState.INTERVIEW, ApplicationState.OFFER),
        (ApplicationState.INTERVIEW, ApplicationState.REJECTED),
        (ApplicationState.OFFER, ApplicationState.WITHDRAWN),
        (ApplicationState.OFFER, ApplicationState.ARCHIVED),
        (ApplicationState.REJECTED, ApplicationState.ARCHIVED),
        (ApplicationState.WITHDRAWN, ApplicationState.ARCHIVED),
        (ApplicationState.DRAFT, ApplicationState.ARCHIVED),
    ],
)
def test_valid_transitions(from_state: ApplicationState, to_state: ApplicationState) -> None:
    assert is_valid_transition(from_state, to_state)


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (ApplicationState.ARCHIVED, ApplicationState.READY),
        (ApplicationState.REJECTED, ApplicationState.SUBMITTED),
        (ApplicationState.WITHDRAWN, ApplicationState.INTERVIEW),
        (ApplicationState.OFFER, ApplicationState.DRAFT),
        (ApplicationState.VIEWED, ApplicationState.SUBMITTED),
        (ApplicationState.INTERVIEW, ApplicationState.READY),
        (ApplicationState.DRAFT, ApplicationState.INTERVIEW),
        (ApplicationState.READY, ApplicationState.OFFER),
    ],
)
def test_invalid_transitions(from_state: ApplicationState, to_state: ApplicationState) -> None:
    assert not is_valid_transition(from_state, to_state)


def test_archived_is_terminal() -> None:
    assert is_valid_transition(ApplicationState.ARCHIVED, ApplicationState.ARCHIVED) is False
    assert is_valid_transition(ApplicationState.ARCHIVED, ApplicationState.DRAFT) is False


def test_application_to_dict() -> None:
    app = JobApplication(
        id=7,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v3",
        company_name="Acme",
        job_title="Backend Engineer",
        status=ApplicationState.SUBMITTED,
        application_package_id=5,
        resume_path="output/resume.pdf",
        cover_letter_path="output/cover.pdf",
        labels=("remote", "priority"),
        submitted_at="2026-08-01T10:00:00",
        created_at="2026-08-01T09:00:00",
        updated_at="2026-08-01T10:00:00",
    )
    data = app.to_dict()
    assert data["id"] == 7
    assert data["status"] == "submitted"
    assert data["labels"] == ["remote", "priority"]
    assert data["application_package_id"] == 5
    assert data["resume_path"] == "output/resume.pdf"


def test_application_defaults() -> None:
    app = JobApplication(
        recommendation_id=1,
        job_id=2,
        profile_id=3,
        profile_version="current",
        company_name="Acme",
        job_title="Dev",
    )
    assert app.status == ApplicationState.DRAFT
    assert app.labels == ()
    assert app.submitted_at is None


def test_event_to_dict() -> None:
    event = ApplicationEvent(
        application_id=1,
        action=ApplicationAction.STATUS_CHANGED,
        actor="cli",
        previous_state=ApplicationState.DRAFT,
        new_state=ApplicationState.READY,
    )
    data = event.to_dict()
    assert data["previous_state"] == "draft"
    assert data["new_state"] == "ready"


def test_note_to_dict() -> None:
    note = ApplicationNote(application_id=1, author="alice", text="Scheduled phone screen")
    assert note.to_dict()["text"] == "Scheduled phone screen"


def test_timeline_to_dict() -> None:
    event = ApplicationTimelineEvent(
        application_id=1, event_type="status_changed", title="Status changed: ready → submitted"
    )
    assert event.to_dict()["event_type"] == "status_changed"


def test_reminder_to_dict() -> None:
    reminder = FollowUpReminder(
        application_id=1,
        due_at="2026-08-05T09:00:00",
        message="Follow up with Acme",
        status=FollowUpStatus.PENDING,
    )
    data = reminder.to_dict()
    assert data["status"] == "pending"
    assert data["due_at"] == "2026-08-05T09:00:00"


def test_outcome_to_dict() -> None:
    outcome = ApplicationOutcome(application_id=1, outcome_type=OutcomeType.HIRED, notes="Signed")
    assert outcome.to_dict()["outcome_type"] == "hired"
