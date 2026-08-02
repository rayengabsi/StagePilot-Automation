"""Integration tests for the Application Execution Engine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.db.models.jobs import Job as JobRecord
from app.db.models.jobs import JobSource, RawJob
from app.db.models.profile import Profile
from app.db.models.recommendation import RecommendationRecord
from app.domain.applications import (
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
from app.domain.approval.package import create_application_package
from app.services.application_service import ApplicationService
from app.services.approval_service import ApprovalService
from sqlalchemy.orm import Session


def _seed_base(db_session: Session) -> tuple[JobSource, Profile]:
    source = JobSource(
        name=f"source-{uuid.uuid4().hex[:8]}",
        type="rss",
        base_url="http://example.com",
    )
    db_session.add(source)
    db_session.flush()
    profile = Profile(name="Test User")
    db_session.add(profile)
    db_session.flush()
    return source, profile


def _seed_job_and_recommendation(
    db_session: Session,
    source: JobSource,
    profile: Profile,
    *,
    company: str,
    title: str,
) -> tuple[JobRecord, RecommendationRecord]:
    raw = RawJob(
        source_id=source.id,
        url="http://example.com/feed.xml",
        raw_payload_json={},
        content_hash=uuid.uuid4().hex,
        discovered_at=datetime.now(UTC),
    )
    db_session.add(raw)
    db_session.flush()
    job = JobRecord(
        raw_job_id=raw.id,
        source_id=source.id,
        url="http://example.com/job",
        title=title,
        company=company,
        location="Remote",
        normalized_hash=uuid.uuid4().hex,
    )
    db_session.add(job)
    db_session.flush()
    recommendation = RecommendationRecord(
        profile_id=profile.id,
        job_id=job.id,
        final_score=85.0,
        ranking_position=1,
        status="active",
    )
    db_session.add(recommendation)
    db_session.flush()
    return job, recommendation


def test_full_lifecycle(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    _job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Backend Engineer"
    )
    svc = ApplicationService(session=db_session)

    app = svc.create_application(
        recommendation_id=rec.id,
        job_id=rec.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Acme",
        job_title="Backend Engineer",
    )
    assert app.status == ApplicationState.DRAFT

    app = svc.change_status(app.id, ApplicationState.READY, "cli")
    assert app.status == ApplicationState.READY

    app = svc.change_status(app.id, ApplicationState.SUBMITTED, "cli")
    assert app.status == ApplicationState.SUBMITTED
    assert app.submitted_at is not None

    app = svc.change_status(app.id, ApplicationState.VIEWED, "cli")
    assert app.status == ApplicationState.VIEWED
    assert app.responded_at is not None

    app = svc.change_status(app.id, ApplicationState.INTERVIEW, "cli")
    assert app.status == ApplicationState.INTERVIEW

    app = svc.change_status(app.id, ApplicationState.OFFER, "cli")
    assert app.status == ApplicationState.OFFER
    assert app.offer_at is not None

    app = svc.archive(app.id, "cli")
    assert app.status == ApplicationState.ARCHIVED
    assert app.archived_at is not None

    history = svc.get_history(app.id)
    actions = [e.action.value for e in history]
    assert actions == [
        "created",
        "status_changed",
        "status_changed",
        "status_changed",
        "status_changed",
        "status_changed",
        "status_changed",
    ]

    timeline = svc.get_timeline(app.id)
    assert len(timeline) == 7


def test_invalid_transition_rejected(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    _job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Engineer"
    )
    svc = ApplicationService(session=db_session)
    app = svc.create_application(
        recommendation_id=rec.id,
        job_id=rec.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Acme",
        job_title="Engineer",
    )
    with pytest.raises(InvalidStateTransitionError):
        svc.change_status(app.id, ApplicationState.OFFER, "cli")


def test_duplicate_application_raises(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    _job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Engineer"
    )
    svc = ApplicationService(session=db_session)
    svc.create_application(
        recommendation_id=rec.id,
        job_id=rec.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Acme",
        job_title="Engineer",
    )
    with pytest.raises(DuplicateApplicationError):
        svc.create_application(
            recommendation_id=rec.id,
            job_id=rec.job_id,
            profile_id=profile.id,
            profile_version="v1",
            company_name="Acme",
            job_title="Engineer",
        )


def test_create_from_approved_package(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Backend Engineer"
    )
    package = create_application_package(
        recommendation_id=rec.id,
        job_id=job.id,
        profile_id=profile.id,
        final_score=85.0,
        snapshot_json='{"recommendation": {"job": {"company": "Acme"}}}',
        documents_json=(
            '{"resume_pdf": "output/resume.pdf", "cover_letter_pdf": "output/cover.pdf"}'
        ),
        profile_version="v1",
    )
    approval = ApprovalService(session=db_session)
    saved = approval.create_package(package)
    approval.enqueue(saved.id)
    approval.start_review(saved.id, "tester")
    approval.approve(saved.id, "tester")

    svc = ApplicationService(session=db_session)
    app = svc.create_from_approved_package(package_id=saved.id)

    assert app.recommendation_id == rec.id
    assert app.application_package_id == saved.id
    assert app.profile_version == "v1"
    assert app.company_name == "Acme"
    assert app.job_title == "Backend Engineer"
    assert app.resume_path == "output/resume.pdf"
    assert app.cover_letter_path == "output/cover.pdf"
    assert app.status == ApplicationState.DRAFT


def test_create_from_non_approved_package_fails(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Engineer"
    )
    package = create_application_package(
        recommendation_id=rec.id,
        job_id=job.id,
        profile_id=profile.id,
        final_score=85.0,
        snapshot_json="{}",
        documents_json="{}",
    )
    approval = ApprovalService(session=db_session)
    saved = approval.create_package(package)

    svc = ApplicationService(session=db_session)
    with pytest.raises(ApplicationError):
        svc.create_from_approved_package(package_id=saved.id)


def test_notes_labels_reminders_outcomes(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    _job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Engineer"
    )
    svc = ApplicationService(session=db_session)
    app = svc.create_application(
        recommendation_id=rec.id,
        job_id=rec.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Acme",
        job_title="Engineer",
    )

    note = svc.add_note(app.id, "alice", "Phone screen booked")
    assert note.text == "Phone screen booked"
    assert len(svc.list_notes(app.id)) == 1

    app = svc.add_label(app.id, "priority", "alice")
    app = svc.add_label(app.id, "remote", "alice")
    assert set(app.labels) == {"priority", "remote"}
    app = svc.remove_label(app.id, "remote", "alice")
    assert app.labels == ("priority",)

    reminder = svc.schedule_follow_up(app.id, "cli", due_at="2099-01-01T09:00:00", message="Nudge")
    assert reminder.status == FollowUpStatus.PENDING
    assert len(svc.due_reminders(datetime(2099, 1, 2, tzinfo=UTC))) == 1

    completed = svc.complete_reminder(reminder.id, "cli")
    assert completed.status == FollowUpStatus.COMPLETED
    assert svc.due_reminders(datetime(2099, 1, 2, tzinfo=UTC)) == []

    reminder2 = svc.schedule_follow_up(
        app.id, "cli", due_at="2099-02-01T09:00:00", message="Nudge 2"
    )
    snoozed = svc.snooze_reminder(reminder2.id, "2099-03-01T09:00:00", "cli")
    assert snoozed.status == FollowUpStatus.SNOOZED
    assert svc.due_reminders(datetime(2099, 2, 15, tzinfo=UTC)) == []

    outcome = svc.record_outcome(app.id, OutcomeType.HIRED, "cli", notes="Signed offer")
    assert outcome.outcome_type == OutcomeType.HIRED
    assert svc.get_outcome(app.id).outcome_type == OutcomeType.HIRED


def test_reminder_disabled_raises(db_session: Session) -> None:
    from app.config.application_config import ApplicationConfig

    source, profile = _seed_base(db_session)
    _job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Engineer"
    )
    svc = ApplicationService(
        session=db_session,
        config=ApplicationConfig(reminders_enabled=False),
    )
    app = svc.create_application(
        recommendation_id=rec.id,
        job_id=rec.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Acme",
        job_title="Engineer",
    )
    with pytest.raises(ReminderError):
        svc.schedule_follow_up(app.id, "cli")


def test_search_and_filters(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    _j1, rec1 = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Backend Engineer"
    )
    _j2, rec2 = _seed_job_and_recommendation(
        db_session, source, profile, company="Globex", title="Frontend Engineer"
    )
    svc = ApplicationService(session=db_session)
    app1 = svc.create_application(
        recommendation_id=rec1.id,
        job_id=rec1.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Acme",
        job_title="Backend Engineer",
        labels=("remote",),
    )
    svc.create_application(
        recommendation_id=rec2.id,
        job_id=rec2.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Globex",
        job_title="Frontend Engineer",
    )
    svc.change_status(app1.id, ApplicationState.SUBMITTED, "cli")

    by_company = svc.list_applications(company="acme")
    assert len(by_company) == 1
    assert by_company[0].company_name == "Acme"

    by_status = svc.list_applications(status="submitted")
    assert len(by_status) == 1
    assert by_status[0].id == app1.id

    by_label = svc.list_applications(label="remote")
    assert len(by_label) == 1

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    by_date = svc.list_applications(date_from=today, date_to=today)
    assert len(by_date) == 2

    results = svc.search_applications("backend")
    assert len(results) == 1
    assert results[0].company_name == "Acme"


def test_summarize_and_analytics(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    companies = [
        ("Acme", "submitted"),
        ("Globex", "interview"),
        ("Initech", "offer"),
        ("Umbrella", "rejected"),
        ("Wayne", "draft"),
    ]
    svc = ApplicationService(session=db_session)
    for company, final_status in companies:
        _job, rec = _seed_job_and_recommendation(
            db_session, source, profile, company=company, title="Engineer"
        )
        app = svc.create_application(
            recommendation_id=rec.id,
            job_id=rec.job_id,
            profile_id=profile.id,
            profile_version="v1",
            company_name=company,
            job_title="Engineer",
        )
        if final_status != "draft":
            svc.change_status(app.id, ApplicationState.READY, "cli")
            svc.change_status(app.id, ApplicationState.SUBMITTED, "cli")
            if final_status == "interview":
                svc.change_status(app.id, ApplicationState.VIEWED, "cli")
                svc.change_status(app.id, ApplicationState.INTERVIEW, "cli")
            elif final_status == "offer":
                svc.change_status(app.id, ApplicationState.VIEWED, "cli")
                svc.change_status(app.id, ApplicationState.INTERVIEW, "cli")
                svc.change_status(app.id, ApplicationState.OFFER, "cli")
            elif final_status == "rejected":
                svc.change_status(app.id, ApplicationState.REJECTED, "cli")

    summary = svc.summarize()
    assert summary["total"] == 5
    assert summary["by_status"]["draft"] == 1
    assert summary["by_status"]["submitted"] == 1
    assert summary["by_status"]["interview"] == 1
    assert summary["by_status"]["offer"] == 1
    assert summary["by_status"]["rejected"] == 1

    analytics = svc.analytics()
    assert analytics["total"] == 5
    assert analytics["counts"]["submitted"] == 4
    assert analytics["counts"]["interview"] == 2
    assert analytics["counts"]["offer"] == 1
    assert analytics["counts"]["rejected"] == 1
    assert analytics["rates"]["submission_rate"] == 80.0
    assert analytics["rates"]["interview_rate"] == 50.0
    assert analytics["rates"]["offer_rate"] == 25.0
    assert analytics["rates"]["rejection_rate"] == 25.0


def test_update_application_metadata(db_session: Session) -> None:
    source, profile = _seed_base(db_session)
    _job, rec = _seed_job_and_recommendation(
        db_session, source, profile, company="Acme", title="Engineer"
    )
    svc = ApplicationService(session=db_session)
    app = svc.create_application(
        recommendation_id=rec.id,
        job_id=rec.job_id,
        profile_id=profile.id,
        profile_version="v1",
        company_name="Acme",
        job_title="Engineer",
    )
    updated = svc.update_application(
        app.id, "cli", company_name="Acme Corp", job_title="Senior Engineer"
    )
    assert updated.company_name == "Acme Corp"
    assert updated.job_title == "Senior Engineer"
    actions = [e.action.value for e in svc.get_history(app.id)]
    assert "updated" in actions
