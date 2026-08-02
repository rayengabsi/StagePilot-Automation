from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config.application_config import ApplicationConfig, get_application_config
from app.db.models.applications import FollowUpReminderRecord
from app.db.models.jobs import Job
from app.db.models.recommendation import RecommendationRecord
from app.db.repositories.applications import (
    ApplicationEventRepository,
    ApplicationNoteRepository,
    ApplicationOutcomeRepository,
    ApplicationRepository,
    ApplicationTimelineRepository,
    FollowUpReminderRepository,
)
from app.domain.applications.entities import (
    ApplicationEvent,
    ApplicationNote,
    ApplicationOutcome,
    ApplicationTimelineEvent,
    FollowUpReminder,
    JobApplication,
)
from app.domain.applications.enums import (
    ApplicationAction,
    ApplicationState,
    FollowUpStatus,
    OutcomeType,
    is_valid_transition,
)
from app.domain.applications.errors import (
    ApplicationError,
    DuplicateApplicationError,
    InvalidStateTransitionError,
    ReminderError,
)
from app.domain.approval.enums import ApprovalState
from app.domain.recommendation.enums import RecommendationStatus
from app.services.approval_service import ApprovalService

_SUBMITTED_STATES = frozenset(
    {
        ApplicationState.SUBMITTED,
        ApplicationState.VIEWED,
        ApplicationState.INTERVIEW,
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
    }
)
_VIEWED_STATES = frozenset(
    {
        ApplicationState.VIEWED,
        ApplicationState.INTERVIEW,
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
    }
)
_INTERVIEW_STATES = frozenset(
    {ApplicationState.INTERVIEW, ApplicationState.ASSESSMENT, ApplicationState.OFFER}
)
_RESPONSE_STATES = frozenset(
    {
        ApplicationState.VIEWED,
        ApplicationState.INTERVIEW,
        ApplicationState.ASSESSMENT,
        ApplicationState.OFFER,
        ApplicationState.REJECTED,
    }
)
_CLOSED_STATES = frozenset(
    {ApplicationState.REJECTED, ApplicationState.WITHDRAWN, ApplicationState.ARCHIVED}
)


class ApplicationService:
    """Owns ALL application lifecycle business logic.

    Responsibilities:
        - Transform approved recommendations into tracked applications
        - State transitions with a validated state machine
        - Audit history and timeline events
        - Notes, labels, follow-up reminders, and outcome tracking
        - Search, summarize, and analytics
    """

    def __init__(
        self,
        session: Session,
        config: ApplicationConfig | None = None,
        approval_service: ApprovalService | None = None,
    ) -> None:
        self._session = session
        self._config = config or get_application_config()
        self._approval_service = approval_service or ApprovalService(session=session)
        self._app_repo = ApplicationRepository(session)
        self._event_repo = ApplicationEventRepository(session)
        self._note_repo = ApplicationNoteRepository(session)
        self._timeline_repo = ApplicationTimelineRepository(session)
        self._reminder_repo = FollowUpReminderRepository(session)
        self._outcome_repo = ApplicationOutcomeRepository(session)

    # ── Creation ───────────────────────────────────────────────────

    def create_application(
        self,
        recommendation_id: int,
        job_id: int,
        profile_id: int,
        profile_version: str,
        company_name: str,
        job_title: str,
        *,
        application_package_id: int | None = None,
        resume_path: str = "",
        cover_letter_path: str = "",
        actor: str = "system",
        labels: tuple[str, ...] = (),
    ) -> JobApplication:
        """Create a new application in the Draft state."""
        self._assert_no_open_application(recommendation_id)
        merged_labels = tuple(sorted(set(labels) | set(self._config.default_labels)))
        application = JobApplication(
            recommendation_id=recommendation_id,
            job_id=job_id,
            profile_id=profile_id,
            profile_version=profile_version,
            company_name=company_name,
            job_title=job_title,
            application_package_id=application_package_id,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            labels=merged_labels,
        )
        saved = self._app_repo.save(application)
        self._record_event(
            saved.id,
            ApplicationAction.CREATED,
            actor,
            comment="Application created",
            new_state=ApplicationState.DRAFT,
        )
        self._timeline_repo.add(
            ApplicationTimelineEvent(
                application_id=saved.id,
                event_type="created",
                title="Application created",
                description=f"{company_name} — {job_title}",
            )
        )
        return saved

    def create_from_approved_package(self, package_id: int, actor: str = "cli") -> JobApplication:
        """Transform an approved application package into a tracked application."""
        package = self._approval_service.get_package(package_id)
        if package.status != ApprovalState.APPROVED:
            msg = (
                f"Package {package_id} has status {package.status.value}; "
                "expected 'approved' before creating an application"
            )
            raise ApplicationError(msg)
        self._assert_no_open_application(package.recommendation_id)

        job = self._session.get(Job, package.job_id)
        company_name = job.company if job else ""
        job_title = job.title if job else ""
        documents = self._approval_service.get_documents(package_id)
        resume_path = documents.get("resume_pdf") or documents.get("resume_docx") or ""
        cover_letter_path = (
            documents.get("cover_letter_pdf") or documents.get("cover_letter_docx") or ""
        )

        application = self.create_application(
            recommendation_id=package.recommendation_id,
            job_id=package.job_id,
            profile_id=package.profile_id,
            profile_version=package.profile_version,
            company_name=company_name,
            job_title=job_title,
            application_package_id=package.id,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            actor=actor,
        )
        self._mark_recommendation_applied(package.recommendation_id)
        return application

    # ── Reads ──────────────────────────────────────────────────────

    def get_application(self, application_id: int) -> JobApplication:
        return self._app_repo.get_by_id(application_id)

    def list_applications(
        self,
        status: ApplicationState | str | None = None,
        company: str | None = None,
        label: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobApplication]:
        status_value = status.value if isinstance(status, ApplicationState) else status
        return self._app_repo.list_all(
            status=status_value,
            company=company,
            label=label,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    def search_applications(self, query: str, limit: int = 20) -> list[JobApplication]:
        return self._app_repo.search(query, limit=limit)

    # ── Updates ────────────────────────────────────────────────────

    def update_application(
        self,
        application_id: int,
        actor: str,
        *,
        job_title: str | None = None,
        company_name: str | None = None,
        resume_path: str | None = None,
        cover_letter_path: str | None = None,
        comment: str = "",
    ) -> JobApplication:
        self._app_repo.get_by_id(application_id)
        updated = self._app_repo.update(
            application_id,
            company_name=company_name,
            job_title=job_title,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
        )
        self._record_event(
            application_id,
            ApplicationAction.UPDATED,
            actor,
            comment=comment or "Application updated",
        )
        return updated

    def change_status(
        self,
        application_id: int,
        new_status: ApplicationState | str,
        actor: str,
        comment: str = "",
    ) -> JobApplication:
        application = self._app_repo.get_by_id(application_id)
        target = ApplicationState(new_status) if isinstance(new_status, str) else new_status
        if target == application.status:
            return application
        if not is_valid_transition(application.status, target):
            msg = f"Invalid transition: {application.status.value} -> {target.value}"
            raise InvalidStateTransitionError(msg)

        now = datetime.now(UTC)
        kwargs: dict[str, Any] = {"status": target}
        if target == ApplicationState.SUBMITTED and application.submitted_at is None:
            kwargs["submitted_at"] = now
        if target in _RESPONSE_STATES and application.responded_at is None:
            kwargs["responded_at"] = now
        if target == ApplicationState.OFFER and application.offer_at is None:
            kwargs["offer_at"] = now
        if target == ApplicationState.ARCHIVED and application.archived_at is None:
            kwargs["archived_at"] = now
        updated = self._app_repo.update(application_id, **kwargs)

        self._record_event(
            application_id,
            ApplicationAction.STATUS_CHANGED,
            actor,
            comment=comment,
            previous_state=application.status,
            new_state=target,
        )
        self._timeline_repo.add(
            ApplicationTimelineEvent(
                application_id=application_id,
                event_type="status_changed",
                title=f"Status changed: {application.status.value} → {target.value}",
                description=comment,
            ),
            occurred_at=now,
        )
        return updated

    def archive(self, application_id: int, actor: str, comment: str = "") -> JobApplication:
        return self.change_status(application_id, ApplicationState.ARCHIVED, actor, comment)

    # ── Labels ─────────────────────────────────────────────────────

    def set_labels(
        self, application_id: int, labels: tuple[str, ...], actor: str
    ) -> JobApplication:
        self._app_repo.get_by_id(application_id)
        updated = self._app_repo.update(application_id, labels=tuple(sorted(set(labels))))
        self._record_event(
            application_id,
            ApplicationAction.LABEL_ADDED,
            actor,
            comment=(
                f"Labels set: {', '.join(updated.labels)}" if updated.labels else "Labels cleared"
            ),
        )
        return updated

    def add_label(self, application_id: int, label: str, actor: str) -> JobApplication:
        application = self._app_repo.get_by_id(application_id)
        labels = set(application.labels)
        labels.add(label)
        updated = self._app_repo.update(application_id, labels=tuple(sorted(labels)))
        self._record_event(
            application_id,
            ApplicationAction.LABEL_ADDED,
            actor,
            comment=f"Added label: {label}",
        )
        return updated

    def remove_label(self, application_id: int, label: str, actor: str) -> JobApplication:
        application = self._app_repo.get_by_id(application_id)
        labels = set(application.labels)
        labels.discard(label)
        updated = self._app_repo.update(application_id, labels=tuple(sorted(labels)))
        self._record_event(
            application_id,
            ApplicationAction.LABEL_REMOVED,
            actor,
            comment=f"Removed label: {label}",
        )
        return updated

    # ── Notes ──────────────────────────────────────────────────────

    def add_note(self, application_id: int, author: str, text: str) -> ApplicationNote:
        self._app_repo.get_by_id(application_id)
        note = self._note_repo.add(
            ApplicationNote(application_id=application_id, author=author, text=text)
        )
        self._record_event(
            application_id,
            ApplicationAction.NOTE_ADDED,
            author,
            comment=f"Note added by {author}",
        )
        return note

    def list_notes(self, application_id: int) -> list[ApplicationNote]:
        return self._note_repo.list_for_application(application_id)

    # ── Timeline & history ─────────────────────────────────────────

    def add_timeline_event(
        self,
        application_id: int,
        event_type: str,
        title: str,
        description: str = "",
        occurred_at: str | None = None,
    ) -> ApplicationTimelineEvent:
        self._app_repo.get_by_id(application_id)
        occurred = datetime.fromisoformat(occurred_at) if occurred_at else datetime.now(UTC)
        return self._timeline_repo.add(
            ApplicationTimelineEvent(
                application_id=application_id,
                event_type=event_type,
                title=title,
                description=description,
            ),
            occurred_at=occurred,
        )

    def get_timeline(self, application_id: int) -> list[ApplicationTimelineEvent]:
        return self._timeline_repo.list_for_application(application_id)

    def get_history(self, application_id: int) -> list[ApplicationEvent]:
        return self._event_repo.list_for_application(application_id)

    # ── Follow-up reminders ────────────────────────────────────────

    def schedule_follow_up(
        self,
        application_id: int,
        actor: str,
        *,
        due_at: str | None = None,
        due_days: int | None = None,
        message: str = "Follow up on application",
    ) -> FollowUpReminder:
        if not self._config.reminders_enabled:
            msg = "Follow-up reminders are disabled by configuration"
            raise ReminderError(msg)
        self._app_repo.get_by_id(application_id)
        now = datetime.now(UTC)
        if due_days is not None:
            due = now + timedelta(days=due_days)
        elif due_at is not None:
            due = datetime.fromisoformat(due_at)
        else:
            due = now + timedelta(days=self._config.follow_up_default_days)
        reminder = self._reminder_repo.add(
            FollowUpReminder(
                application_id=application_id,
                due_at=due.isoformat(),
                message=message,
            )
        )
        self._record_event(
            application_id,
            ApplicationAction.REMINDER_SCHEDULED,
            actor,
            comment=f"Follow-up scheduled for {due.isoformat()}: {message}",
        )
        self._timeline_repo.add(
            ApplicationTimelineEvent(
                application_id=application_id,
                event_type="reminder_scheduled",
                title="Follow-up scheduled",
                description=f"Due {due.isoformat()}: {message}",
            ),
            occurred_at=now,
        )
        return reminder

    def complete_reminder(self, reminder_id: int, actor: str) -> FollowUpReminder:
        reminder = self._reminder_repo.get_by_id(reminder_id)
        if reminder.status == FollowUpStatus.COMPLETED:
            return reminder
        updated = self._reminder_repo.update_status(
            reminder_id, FollowUpStatus.COMPLETED, completed_at=datetime.now(UTC)
        )
        self._record_event(
            reminder.application_id,
            ApplicationAction.REMINDER_COMPLETED,
            actor,
            comment="Follow-up completed",
        )
        return updated

    def cancel_reminder(self, reminder_id: int, actor: str) -> FollowUpReminder:
        reminder = self._reminder_repo.get_by_id(reminder_id)
        if reminder.status == FollowUpStatus.CANCELLED:
            return reminder
        updated = self._reminder_repo.update_status(reminder_id, FollowUpStatus.CANCELLED)
        self._record_event(
            reminder.application_id,
            ApplicationAction.REMINDER_CANCELLED,
            actor,
            comment="Follow-up cancelled",
        )
        return updated

    def snooze_reminder(self, reminder_id: int, new_due_at: str, actor: str) -> FollowUpReminder:
        reminder = self._reminder_repo.get_by_id(reminder_id)
        due = datetime.fromisoformat(new_due_at)
        stmt = (
            update(FollowUpReminderRecord)
            .where(FollowUpReminderRecord.id == reminder_id)
            .values(due_at=due, status=FollowUpStatus.SNOOZED.value)
        )
        self._session.execute(stmt)
        self._session.flush()
        updated = self._reminder_repo.get_by_id(reminder_id)
        self._record_event(
            reminder.application_id,
            ApplicationAction.REMINDER_SNOOZED,
            actor,
            comment=f"Follow-up snoozed until {new_due_at}",
        )
        return updated

    def list_reminders(
        self,
        status: FollowUpStatus | str | None = None,
        due_before: str | None = None,
        limit: int = 50,
    ) -> list[FollowUpReminder]:
        status_value = status.value if isinstance(status, FollowUpStatus) else status
        parsed = (
            FollowUpStatus(status_value) if isinstance(status_value, str) and status_value else None
        )
        due = datetime.fromisoformat(due_before) if due_before else None
        return self._reminder_repo.list_all(status=parsed, due_before=due, limit=limit)

    def due_reminders(self, as_of: datetime) -> list[FollowUpReminder]:
        return self._reminder_repo.list_due(as_of)

    # ── Outcomes ───────────────────────────────────────────────────

    def record_outcome(
        self,
        application_id: int,
        outcome_type: OutcomeType | str,
        actor: str,
        notes: str = "",
    ) -> ApplicationOutcome:
        self._app_repo.get_by_id(application_id)
        outcome_enum = OutcomeType(outcome_type) if isinstance(outcome_type, str) else outcome_type
        outcome = self._outcome_repo.add(
            ApplicationOutcome(
                application_id=application_id,
                outcome_type=outcome_enum,
                notes=notes,
            )
        )
        self._record_event(
            application_id,
            ApplicationAction.OUTCOME_RECORDED,
            actor,
            comment=f"Outcome recorded: {outcome_enum.value}",
        )
        self._timeline_repo.add(
            ApplicationTimelineEvent(
                application_id=application_id,
                event_type="outcome_recorded",
                title=f"Outcome recorded: {outcome_enum.value}",
                description=notes,
            )
        )
        return outcome

    def get_outcome(self, application_id: int) -> ApplicationOutcome | None:
        return self._outcome_repo.get_for_application(application_id)

    # ── Summaries & analytics ──────────────────────────────────────

    def summarize(self) -> dict[str, Any]:
        return {
            "total": self._app_repo.count_all(),
            "by_status": self._app_repo.group_by_status(),
            "by_company": self._app_repo.group_by_company(),
        }

    def analytics(self) -> dict[str, Any]:
        applications = self._app_repo.list_all_unbounded()
        total = len(applications)
        submitted = [a for a in applications if a.status in _SUBMITTED_STATES]
        viewed = [a for a in applications if a.status in _VIEWED_STATES]
        interview = [a for a in applications if a.status in _INTERVIEW_STATES]
        offers = [a for a in applications if a.status == ApplicationState.OFFER]
        rejected = [a for a in applications if a.status == ApplicationState.REJECTED]
        withdrawn = [a for a in applications if a.status == ApplicationState.WITHDRAWN]
        active = [a for a in applications if a.status not in _CLOSED_STATES]
        hired = [
            a
            for a in offers
            if self._outcome_repo.get_for_application(a.id) is not None
            and self._outcome_repo.get_for_application(a.id).outcome_type == OutcomeType.HIRED
        ]
        response_times = [
            (
                datetime.fromisoformat(a.responded_at) - datetime.fromisoformat(a.submitted_at)
            ).total_seconds()
            / 86400
            for a in applications
            if a.submitted_at and a.responded_at
        ]

        def _pct(numerator: int, denominator: int) -> float:
            if denominator <= 0:
                return 0.0
            return round(numerator / denominator * 100, 1)

        return {
            "total": total,
            "counts": {
                "submitted": len(submitted),
                "viewed": len(viewed),
                "interview": len(interview),
                "offer": len(offers),
                "rejected": len(rejected),
                "withdrawn": len(withdrawn),
                "active": len(active),
                "hired": len(hired),
            },
            "rates": {
                "submission_rate": _pct(len(submitted), total),
                "interview_rate": _pct(len(interview), len(submitted)),
                "offer_rate": _pct(len(offers), len(submitted)),
                "rejection_rate": _pct(len(rejected), len(submitted)),
                "offer_acceptance_rate": _pct(len(hired), len(offers)),
            },
            "average_response_time_days": (
                round(sum(response_times) / len(response_times), 1) if response_times else 0.0
            ),
            "conversions": {
                "submitted": _pct(len(submitted), total),
                "viewed": _pct(len(viewed), len(submitted)),
                "interview": _pct(len(interview), len(viewed)),
                "offer": _pct(len(offers), len(interview)),
                "hired": _pct(len(hired), len(offers)),
            },
        }

    # ── Internal helpers ───────────────────────────────────────────

    def _assert_no_open_application(self, recommendation_id: int) -> None:
        existing = self._app_repo.list_for_recommendation(recommendation_id)
        if any(e.status not in _CLOSED_STATES for e in existing):
            msg = f"Recommendation {recommendation_id} already has an open application"
            raise DuplicateApplicationError(msg)

    def _mark_recommendation_applied(self, recommendation_id: int) -> None:
        stmt = (
            update(RecommendationRecord)
            .where(RecommendationRecord.id == recommendation_id)
            .values(status=RecommendationStatus.APPLIED.value)
        )
        self._session.execute(stmt)
        self._session.flush()

    def _record_event(
        self,
        application_id: int,
        action: ApplicationAction,
        actor: str,
        comment: str = "",
        previous_state: ApplicationState | None = None,
        new_state: ApplicationState | None = None,
    ) -> None:
        event = ApplicationEvent(
            application_id=application_id,
            action=action,
            actor=actor,
            comment=comment,
            previous_state=previous_state,
            new_state=new_state,
        )
        self._event_repo.record(event)
