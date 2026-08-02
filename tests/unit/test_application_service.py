from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from app.config.application_config import ApplicationConfig
from app.domain.applications.entities import (
    ApplicationNote,
    ApplicationOutcome,
    FollowUpReminder,
    JobApplication,
)
from app.domain.applications.enums import (
    ApplicationState,
    FollowUpStatus,
    OutcomeType,
)
from app.domain.applications.errors import (
    ApplicationError,
    DuplicateApplicationError,
    InvalidStateTransitionError,
    ReminderError,
)
from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.enums import ApprovalState
from app.services.application_service import ApplicationService


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def config() -> ApplicationConfig:
    return ApplicationConfig(reminders_enabled=True, follow_up_default_days=3)


@pytest.fixture
def mock_approval_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def app_domain() -> JobApplication:
    return JobApplication(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        status=ApplicationState.DRAFT,
        created_at="2026-08-01T09:00:00",
        updated_at="2026-08-01T09:00:00",
    )


@pytest.fixture
def submitted_app() -> JobApplication:
    return JobApplication(
        id=2,
        recommendation_id=11,
        job_id=21,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        status=ApplicationState.SUBMITTED,
        submitted_at="2026-08-01T10:00:00",
        created_at="2026-08-01T09:00:00",
        updated_at="2026-08-01T10:00:00",
    )


def _make_service(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> ApplicationService:
    svc = ApplicationService(session=mock_session, config=config)
    svc._approval_service = mock_approval_service
    svc._app_repo = MagicMock()
    svc._event_repo = MagicMock()
    svc._note_repo = MagicMock()
    svc._timeline_repo = MagicMock()
    svc._reminder_repo = MagicMock()
    svc._outcome_repo = MagicMock()
    return svc


def test_create_application(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.list_for_recommendation.return_value = []
    saved = JobApplication(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
    )
    svc._app_repo.save.return_value = saved

    result = svc.create_application(
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        actor="cli",
    )
    assert result.id == 1
    svc._app_repo.save.assert_called_once()
    svc._event_repo.record.assert_called_once()
    svc._timeline_repo.add.assert_called_once()


def test_create_application_duplicate_raises(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.list_for_recommendation.return_value = [app_domain]

    with pytest.raises(DuplicateApplicationError):
        svc.create_application(
            recommendation_id=10,
            job_id=20,
            profile_id=30,
            profile_version="v2",
            company_name="Acme",
            job_title="Backend Engineer",
        )


def test_create_from_approved_package(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    package = ApplicationPackage(
        id=5,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash",
        status=ApprovalState.APPROVED,
        profile_version="v2",
        template_name="modern",
        theme_name="default",
    )
    mock_approval_service.get_package.return_value = package
    mock_approval_service.get_documents.return_value = {
        "resume_pdf": "output/resume.pdf",
        "cover_letter_pdf": "output/cover.pdf",
    }
    job_record = MagicMock()
    job_record.company = "Acme"
    job_record.title = "Backend Engineer"
    mock_session.get.return_value = job_record
    svc._app_repo.list_for_recommendation.return_value = []
    saved = JobApplication(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        application_package_id=5,
        resume_path="output/resume.pdf",
        cover_letter_path="output/cover.pdf",
    )
    svc._app_repo.save.return_value = saved

    result = svc.create_from_approved_package(package_id=5, actor="cli")
    assert result.id == 1
    assert result.application_package_id == 5
    assert result.resume_path == "output/resume.pdf"
    assert result.cover_letter_path == "output/cover.pdf"
    mock_approval_service.get_package.assert_called_once_with(5)
    mock_session.execute.assert_called_once()


def test_create_from_non_approved_package_raises(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    package = ApplicationPackage(
        id=5,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash",
        status=ApprovalState.QUEUED,
        profile_version="v2",
        template_name="modern",
        theme_name="default",
    )
    mock_approval_service.get_package.return_value = package

    with pytest.raises(ApplicationError):
        svc.create_from_approved_package(package_id=5)


def test_get_application(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    assert svc.get_application(1) == app_domain


def test_change_status_valid(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    updated = JobApplication(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        status=ApplicationState.READY,
    )
    svc._app_repo.update.return_value = updated

    result = svc.change_status(1, ApplicationState.READY, "cli")
    assert result.status == ApplicationState.READY
    svc._event_repo.record.assert_called_once()
    svc._timeline_repo.add.assert_called_once()


def test_change_status_sets_submitted_at(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    ready = JobApplication(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        status=ApplicationState.READY,
    )
    svc._app_repo.get_by_id.return_value = ready
    submitted = JobApplication(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        status=ApplicationState.SUBMITTED,
        submitted_at="2026-08-01T12:00:00",
        responded_at=None,
    )
    svc._app_repo.update.return_value = submitted

    result = svc.change_status(1, ApplicationState.SUBMITTED, "cli")
    kwargs = svc._app_repo.update.call_args.kwargs
    assert kwargs["status"] == ApplicationState.SUBMITTED
    assert kwargs["submitted_at"] is not None
    assert result.status == ApplicationState.SUBMITTED


def test_change_status_invalid_raises(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    submitted_app: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = submitted_app

    with pytest.raises(InvalidStateTransitionError):
        svc.change_status(2, ApplicationState.DRAFT, "cli")


def test_archive(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    submitted_app: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = submitted_app
    archived = JobApplication(
        id=2,
        recommendation_id=11,
        job_id=21,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        status=ApplicationState.ARCHIVED,
        archived_at="2026-08-02T00:00:00",
    )
    svc._app_repo.update.return_value = archived

    result = svc.archive(2, "cli")
    assert result.status == ApplicationState.ARCHIVED
    assert svc._app_repo.update.call_args.kwargs["archived_at"] is not None


def test_labels_add_remove(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    labelled = JobApplication(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        profile_version="v2",
        company_name="Acme",
        job_title="Backend Engineer",
        labels=("priority", "remote"),
    )
    svc._app_repo.update.return_value = labelled

    result = svc.add_label(1, "priority", "cli")
    assert "priority" in result.labels
    assert svc._app_repo.update.call_args.kwargs["labels"] == ("priority",)


def test_set_labels(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    svc._app_repo.update.return_value = app_domain

    svc.set_labels(1, ("a", "b"), "cli")
    assert svc._app_repo.update.call_args.kwargs["labels"] == ("a", "b")


def test_add_note(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    note = ApplicationNote(application_id=1, author="alice", text="Phone screen booked")
    svc._note_repo.add.return_value = note

    result = svc.add_note(1, "alice", "Phone screen booked")
    assert result.text == "Phone screen booked"
    svc._event_repo.record.assert_called_once()


def test_schedule_follow_up_due_days(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    svc._reminder_repo.add.return_value = FollowUpReminder(
        application_id=1, due_at="2026-08-05T00:00:00", message="Follow up"
    )

    result = svc.schedule_follow_up(1, "cli", due_days=3, message="Follow up")
    assert result.due_at == "2026-08-05T00:00:00"
    svc._event_repo.record.assert_called_once()


def test_schedule_follow_up_default_days(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    svc._reminder_repo.add.return_value = FollowUpReminder(
        application_id=1, due_at="2026-08-04T00:00:00", message="Follow up"
    )

    before = datetime.now(UTC)
    svc.schedule_follow_up(1, "cli")
    after = datetime.now(UTC)
    captured = svc._reminder_repo.add.call_args.args[0]
    due = datetime.fromisoformat(captured.due_at)
    assert before <= due <= after.replace(day=after.day + config.follow_up_default_days)


def test_schedule_follow_up_disabled_raises(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    disabled = ApplicationConfig(reminders_enabled=False)
    svc = _make_service(mock_session, disabled, mock_approval_service)

    with pytest.raises(ReminderError):
        svc.schedule_follow_up(1, "cli")


def test_complete_reminder(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    pending = FollowUpReminder(
        id=9, application_id=1, due_at="2026-08-05T00:00:00", message="Follow up"
    )
    svc._reminder_repo.get_by_id.return_value = pending
    completed = FollowUpReminder(
        id=9,
        application_id=1,
        due_at="2026-08-05T00:00:00",
        message="Follow up",
        status=FollowUpStatus.COMPLETED,
        completed_at="2026-08-02T00:00:00",
    )
    svc._reminder_repo.update_status.return_value = completed

    result = svc.complete_reminder(9, "cli")
    assert result.status == FollowUpStatus.COMPLETED
    svc._event_repo.record.assert_called_once()


def test_cancel_reminder(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._reminder_repo.get_by_id.return_value = FollowUpReminder(
        id=9, application_id=1, due_at="2026-08-05T00:00:00", message="Follow up"
    )
    svc._reminder_repo.update_status.return_value = FollowUpReminder(
        id=9,
        application_id=1,
        due_at="2026-08-05T00:00:00",
        message="Follow up",
        status=FollowUpStatus.CANCELLED,
    )

    result = svc.cancel_reminder(9, "cli")
    assert result.status == FollowUpStatus.CANCELLED


def test_snooze_reminder(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._reminder_repo.get_by_id.return_value = FollowUpReminder(
        id=9, application_id=1, due_at="2026-08-05T00:00:00", message="Follow up"
    )
    svc._reminder_repo.get_by_id.return_value = FollowUpReminder(
        id=9,
        application_id=1,
        due_at="2026-08-10T00:00:00",
        message="Follow up",
        status=FollowUpStatus.SNOOZED,
    )

    result = svc.snooze_reminder(9, "2026-08-10T00:00:00", "cli")
    assert result.status == FollowUpStatus.SNOOZED
    mock_session.execute.assert_called_once()


def test_record_outcome(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
    app_domain: JobApplication,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.get_by_id.return_value = app_domain
    svc._outcome_repo.add.return_value = ApplicationOutcome(
        application_id=1, outcome_type=OutcomeType.HIRED, notes="Signed offer"
    )

    result = svc.record_outcome(1, OutcomeType.HIRED, "cli", notes="Signed offer")
    assert result.outcome_type == OutcomeType.HIRED
    svc._event_repo.record.assert_called_once()
    svc._timeline_repo.add.assert_called_once()


def test_analytics_empty(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.list_all_unbounded.return_value = []

    result = svc.analytics()
    assert result["total"] == 0
    assert result["average_response_time_days"] == 0.0
    assert result["rates"]["submission_rate"] == 0.0


def test_analytics_rates(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)

    def _app(i: int, status: ApplicationState) -> JobApplication:
        return JobApplication(
            id=i,
            recommendation_id=i,
            job_id=i,
            profile_id=30,
            profile_version="v2",
            company_name="Acme",
            job_title="Engineer",
            status=status,
            submitted_at="2026-08-01T10:00:00" if status != ApplicationState.DRAFT else None,
            responded_at="2026-08-03T10:00:00"
            if status in (ApplicationState.VIEWED, ApplicationState.INTERVIEW)
            else None,
        )

    apps = [
        _app(1, ApplicationState.INTERVIEW),
        _app(2, ApplicationState.OFFER),
        _app(3, ApplicationState.REJECTED),
        _app(4, ApplicationState.DRAFT),
    ]
    svc._app_repo.list_all_unbounded.return_value = apps

    result = svc.analytics()
    assert result["total"] == 4
    assert result["counts"]["submitted"] == 3
    assert result["counts"]["interview"] == 2
    assert result["counts"]["offer"] == 1
    assert result["counts"]["rejected"] == 1
    assert result["rates"]["submission_rate"] == 75.0
    assert result["rates"]["interview_rate"] == round(2 / 3 * 100, 1)
    assert result["rates"]["offer_rate"] == round(1 / 3 * 100, 1)
    assert result["rates"]["rejection_rate"] == round(1 / 3 * 100, 1)
    assert result["average_response_time_days"] == 2.0
    assert result["conversions"]["viewed"] == round(2 / 3 * 100, 1)


def test_summarize(
    mock_session: MagicMock,
    config: ApplicationConfig,
    mock_approval_service: MagicMock,
) -> None:
    svc = _make_service(mock_session, config, mock_approval_service)
    svc._app_repo.count_all.return_value = 3
    svc._app_repo.group_by_status.return_value = {"draft": 2, "submitted": 1}
    svc._app_repo.group_by_company.return_value = {"Acme": 2, "Globex": 1}

    result = svc.summarize()
    assert result["total"] == 3
    assert result["by_status"]["draft"] == 2
    assert result["by_company"]["Acme"] == 2
