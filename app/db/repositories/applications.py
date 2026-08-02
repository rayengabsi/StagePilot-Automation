from __future__ import annotations

from datetime import datetime

from app.db.models.applications import (
    ApplicationEventRecord,
    ApplicationNoteRecord,
    ApplicationOutcomeRecord,
    ApplicationRecord,
    ApplicationTimelineEventRecord,
    FollowUpReminderRecord,
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
)
from app.domain.applications.errors import ApplicationNotFoundError
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, application: JobApplication) -> JobApplication:
        record = ApplicationRecord(
            recommendation_id=application.recommendation_id,
            job_id=application.job_id,
            profile_id=application.profile_id,
            profile_version=application.profile_version,
            company_name=application.company_name,
            job_title=application.job_title,
            status=application.status.value,
            application_package_id=application.application_package_id,
            resume_path=application.resume_path or None,
            cover_letter_path=application.cover_letter_path or None,
            labels_json=list(application.labels),
            submitted_at=_parse_dt(application.submitted_at),
            responded_at=_parse_dt(application.responded_at),
            offer_at=_parse_dt(application.offer_at),
            archived_at=_parse_dt(application.archived_at),
        )
        self._session.add(record)
        self._session.flush()
        return self._to_domain(record)

    def get_by_id(self, application_id: int) -> JobApplication:
        record = self._session.get(ApplicationRecord, application_id)
        if record is None:
            msg = f"Application {application_id} not found"
            raise ApplicationNotFoundError(msg)
        return self._to_domain(record)

    def update(
        self,
        application_id: int,
        *,
        status: ApplicationState | None = None,
        company_name: str | None = None,
        job_title: str | None = None,
        resume_path: str | None = None,
        cover_letter_path: str | None = None,
        labels: tuple[str, ...] | None = None,
        submitted_at: datetime | None = None,
        responded_at: datetime | None = None,
        offer_at: datetime | None = None,
        archived_at: datetime | None = None,
    ) -> JobApplication:
        values: dict = {"updated_at": datetime.now()}
        if status is not None:
            values["status"] = status.value
        if company_name is not None:
            values["company_name"] = company_name
        if job_title is not None:
            values["job_title"] = job_title
        if resume_path is not None:
            values["resume_path"] = resume_path or None
        if cover_letter_path is not None:
            values["cover_letter_path"] = cover_letter_path or None
        if labels is not None:
            values["labels_json"] = list(labels)
        if submitted_at is not None:
            values["submitted_at"] = submitted_at
        if responded_at is not None:
            values["responded_at"] = responded_at
        if offer_at is not None:
            values["offer_at"] = offer_at
        if archived_at is not None:
            values["archived_at"] = archived_at
        stmt = (
            update(ApplicationRecord).where(ApplicationRecord.id == application_id).values(values)
        )
        self._session.execute(stmt)
        self._session.flush()
        return self.get_by_id(application_id)

    def list_for_recommendation(self, recommendation_id: int) -> list[JobApplication]:
        stmt = (
            select(ApplicationRecord)
            .where(ApplicationRecord.recommendation_id == recommendation_id)
            .order_by(ApplicationRecord.created_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in records]

    def list_all(
        self,
        status: str | None = None,
        company: str | None = None,
        label: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobApplication]:
        stmt = select(ApplicationRecord).order_by(ApplicationRecord.created_at.desc())
        if status:
            stmt = stmt.where(ApplicationRecord.status == status)
        if company:
            stmt = stmt.where(ApplicationRecord.company_name.ilike(f"%{company}%"))
        if label:
            stmt = stmt.where(ApplicationRecord.labels_json.like(f'%"{label}"%'))
        if date_from:
            stmt = stmt.where(func.date(ApplicationRecord.created_at) >= date_from)
        if date_to:
            stmt = stmt.where(func.date(ApplicationRecord.created_at) <= date_to)
        stmt = stmt.offset(offset).limit(limit)
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in records]

    def list_all_unbounded(self) -> list[JobApplication]:
        stmt = select(ApplicationRecord).order_by(ApplicationRecord.created_at.asc())
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in records]

    def search(self, query: str, limit: int = 20) -> list[JobApplication]:
        stmt = (
            select(ApplicationRecord)
            .outerjoin(
                ApplicationNoteRecord,
                ApplicationNoteRecord.application_id == ApplicationRecord.id,
            )
            .where(
                or_(
                    ApplicationRecord.company_name.ilike(f"%{query}%"),
                    ApplicationRecord.job_title.ilike(f"%{query}%"),
                    ApplicationNoteRecord.text.ilike(f"%{query}%"),
                )
            )
            .distinct()
            .order_by(ApplicationRecord.created_at.desc())
            .limit(limit)
        )
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in records]

    def count_all(self, status: str | None = None) -> int:
        stmt = select(func.count()).select_from(ApplicationRecord)
        if status:
            stmt = stmt.where(ApplicationRecord.status == status)
        return int(self._session.execute(stmt).scalar_one())

    def group_by_status(self) -> dict[str, int]:
        stmt = (
            select(ApplicationRecord.status, func.count())
            .group_by(ApplicationRecord.status)
            .order_by(ApplicationRecord.status)
        )
        return dict(self._session.execute(stmt).all())

    def group_by_company(self, limit: int = 20) -> dict[str, int]:
        stmt = (
            select(ApplicationRecord.company_name, func.count())
            .group_by(ApplicationRecord.company_name)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return dict(self._session.execute(stmt).all())

    def _to_domain(self, record: ApplicationRecord) -> JobApplication:
        return JobApplication(
            id=record.id,
            recommendation_id=record.recommendation_id,
            job_id=record.job_id,
            profile_id=record.profile_id,
            profile_version=record.profile_version,
            company_name=record.company_name,
            job_title=record.job_title,
            status=ApplicationState(record.status),
            application_package_id=record.application_package_id,
            resume_path=record.resume_path or "",
            cover_letter_path=record.cover_letter_path or "",
            labels=tuple(record.labels_json or []),
            submitted_at=record.submitted_at.isoformat() if record.submitted_at else None,
            responded_at=record.responded_at.isoformat() if record.responded_at else None,
            offer_at=record.offer_at.isoformat() if record.offer_at else None,
            archived_at=record.archived_at.isoformat() if record.archived_at else None,
            created_at=record.created_at.isoformat() if record.created_at else "",
            updated_at=record.updated_at.isoformat() if record.updated_at else "",
        )


class ApplicationEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, event: ApplicationEvent) -> ApplicationEvent:
        record = ApplicationEventRecord(
            application_id=event.application_id,
            action=event.action.value,
            actor=event.actor,
            comment=event.comment,
            previous_state=event.previous_state.value if event.previous_state else None,
            new_state=event.new_state.value if event.new_state else None,
        )
        self._session.add(record)
        self._session.flush()
        return ApplicationEvent(
            id=record.id,
            application_id=record.application_id,
            action=ApplicationAction(record.action),
            actor=record.actor,
            comment=record.comment or "",
            previous_state=(
                ApplicationState(record.previous_state) if record.previous_state else None
            ),
            new_state=ApplicationState(record.new_state) if record.new_state else None,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )

    def list_for_application(self, application_id: int) -> list[ApplicationEvent]:
        stmt = (
            select(ApplicationEventRecord)
            .where(ApplicationEventRecord.application_id == application_id)
            .order_by(ApplicationEventRecord.created_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [
            ApplicationEvent(
                id=r.id,
                application_id=r.application_id,
                action=ApplicationAction(r.action),
                actor=r.actor,
                comment=r.comment or "",
                previous_state=ApplicationState(r.previous_state) if r.previous_state else None,
                new_state=ApplicationState(r.new_state) if r.new_state else None,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ]


class ApplicationNoteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, note: ApplicationNote) -> ApplicationNote:
        record = ApplicationNoteRecord(
            application_id=note.application_id,
            author=note.author,
            text=note.text,
        )
        self._session.add(record)
        self._session.flush()
        return ApplicationNote(
            id=record.id,
            application_id=record.application_id,
            author=record.author,
            text=record.text,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )

    def list_for_application(self, application_id: int) -> list[ApplicationNote]:
        stmt = (
            select(ApplicationNoteRecord)
            .where(ApplicationNoteRecord.application_id == application_id)
            .order_by(ApplicationNoteRecord.created_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [
            ApplicationNote(
                id=r.id,
                application_id=r.application_id,
                author=r.author,
                text=r.text,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ]


class ApplicationTimelineRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        event: ApplicationTimelineEvent,
        occurred_at: datetime | None = None,
    ) -> ApplicationTimelineEvent:
        record = ApplicationTimelineEventRecord(
            application_id=event.application_id,
            event_type=event.event_type,
            title=event.title,
            description=event.description or None,
            occurred_at=occurred_at or datetime.now(),
        )
        self._session.add(record)
        self._session.flush()
        return ApplicationTimelineEvent(
            id=record.id,
            application_id=record.application_id,
            event_type=record.event_type,
            title=record.title,
            description=record.description or "",
            occurred_at=record.occurred_at.isoformat() if record.occurred_at else "",
        )

    def list_for_application(self, application_id: int) -> list[ApplicationTimelineEvent]:
        stmt = (
            select(ApplicationTimelineEventRecord)
            .where(ApplicationTimelineEventRecord.application_id == application_id)
            .order_by(ApplicationTimelineEventRecord.occurred_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [
            ApplicationTimelineEvent(
                id=r.id,
                application_id=r.application_id,
                event_type=r.event_type,
                title=r.title,
                description=r.description or "",
                occurred_at=r.occurred_at.isoformat() if r.occurred_at else "",
            )
            for r in records
        ]


class FollowUpReminderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, reminder: FollowUpReminder) -> FollowUpReminder:
        record = FollowUpReminderRecord(
            application_id=reminder.application_id,
            due_at=_parse_dt(reminder.due_at),
            message=reminder.message,
            status=reminder.status.value,
            completed_at=_parse_dt(reminder.completed_at),
        )
        self._session.add(record)
        self._session.flush()
        return self._to_domain(record)

    def get_by_id(self, reminder_id: int) -> FollowUpReminder:
        record = self._session.get(FollowUpReminderRecord, reminder_id)
        if record is None:
            msg = f"Follow-up reminder {reminder_id} not found"
            raise ApplicationNotFoundError(msg)
        return self._to_domain(record)

    def update_status(
        self, reminder_id: int, status: FollowUpStatus, completed_at: datetime | None = None
    ) -> FollowUpReminder:
        values: dict = {"status": status.value}
        if completed_at is not None:
            values["completed_at"] = completed_at
        stmt = (
            update(FollowUpReminderRecord)
            .where(FollowUpReminderRecord.id == reminder_id)
            .values(values)
        )
        self._session.execute(stmt)
        self._session.flush()
        return self.get_by_id(reminder_id)

    def list_all(
        self,
        status: FollowUpStatus | None = None,
        due_before: datetime | None = None,
        limit: int = 50,
    ) -> list[FollowUpReminder]:
        stmt = select(FollowUpReminderRecord).order_by(FollowUpReminderRecord.due_at.asc())
        if status:
            stmt = stmt.where(FollowUpReminderRecord.status == status.value)
        if due_before is not None:
            stmt = stmt.where(FollowUpReminderRecord.due_at <= due_before)
        stmt = stmt.limit(limit)
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in records]

    def list_due(self, as_of: datetime) -> list[FollowUpReminder]:
        stmt = (
            select(FollowUpReminderRecord)
            .where(
                FollowUpReminderRecord.status.in_(
                    [FollowUpStatus.PENDING.value, FollowUpStatus.SNOOZED.value]
                ),
                FollowUpReminderRecord.due_at <= as_of,
            )
            .order_by(FollowUpReminderRecord.due_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in records]

    def _to_domain(self, record: FollowUpReminderRecord) -> FollowUpReminder:
        return FollowUpReminder(
            id=record.id,
            application_id=record.application_id,
            due_at=record.due_at.isoformat() if record.due_at else "",
            message=record.message,
            status=FollowUpStatus(record.status),
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )


class ApplicationOutcomeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, outcome: ApplicationOutcome) -> ApplicationOutcome:
        record = ApplicationOutcomeRecord(
            application_id=outcome.application_id,
            outcome_type=outcome.outcome_type.value,
            notes=outcome.notes or None,
        )
        self._session.add(record)
        self._session.flush()
        return ApplicationOutcome(
            id=record.id,
            application_id=record.application_id,
            outcome_type=OutcomeType(record.outcome_type),
            notes=record.notes or "",
            recorded_at=record.recorded_at.isoformat() if record.recorded_at else "",
        )

    def get_for_application(self, application_id: int) -> ApplicationOutcome | None:
        stmt = (
            select(ApplicationOutcomeRecord)
            .where(ApplicationOutcomeRecord.application_id == application_id)
            .order_by(ApplicationOutcomeRecord.recorded_at.desc())
        )
        record = self._session.execute(stmt).scalars().first()
        if record is None:
            return None
        return ApplicationOutcome(
            id=record.id,
            application_id=record.application_id,
            outcome_type=OutcomeType(record.outcome_type),
            notes=record.notes or "",
            recorded_at=record.recorded_at.isoformat() if record.recorded_at else "",
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)
