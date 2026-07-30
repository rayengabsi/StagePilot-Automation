from __future__ import annotations

from datetime import datetime

from app.db.models.approval import (
    ApplicationPackageRecord,
    ApprovalCommentRecord,
    ApprovalEventRecord,
    ApprovalQueueRecord,
)
from app.domain.approval.entities import (
    ApplicationPackage,
    ApprovalComment,
    ApprovalEvent,
)
from app.domain.approval.enums import ApprovalAction, ApprovalState
from app.domain.approval.errors import PackageNotFoundError
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session


class ApplicationPackageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, package: ApplicationPackage) -> ApplicationPackage:
        record = ApplicationPackageRecord(
            recommendation_id=package.recommendation_id,
            job_id=package.job_id,
            profile_id=package.profile_id,
            final_score=package.final_score,
            status=package.status.value,
            priority=package.priority,
            revision_number=package.revision_number,
            telegram_message_id=package.telegram_message_id,
            snapshot_json=package.snapshot_json,
            documents_json=package.documents_json,
            application_hash=package.application_hash,
            profile_version=package.profile_version,
            template_name=package.template_name,
            theme_name=package.theme_name,
        )
        self._session.add(record)
        self._session.flush()
        return self._to_domain(record)

    def get_by_id(self, package_id: int) -> ApplicationPackage:
        record = self._session.get(ApplicationPackageRecord, package_id)
        if record is None:
            msg = f"Application package {package_id} not found"
            raise PackageNotFoundError(msg)
        return self._to_domain(record)

    def get_by_hash(self, hash_value: str) -> ApplicationPackage | None:
        stmt = select(ApplicationPackageRecord).where(
            ApplicationPackageRecord.application_hash == hash_value
        )
        record = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(record) if record else None

    def update_status(self, package_id: int, status: ApprovalState) -> None:
        stmt = (
            update(ApplicationPackageRecord)
            .where(ApplicationPackageRecord.id == package_id)
            .values(status=status.value, updated_at=datetime.now())
        )
        self._session.execute(stmt)
        self._session.flush()

    def update_message_id(self, package_id: int, message_id: int) -> None:
        stmt = (
            update(ApplicationPackageRecord)
            .where(ApplicationPackageRecord.id == package_id)
            .values(telegram_message_id=message_id, updated_at=datetime.now())
        )
        self._session.execute(stmt)
        self._session.flush()

    def list_all(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ApplicationPackage]:
        stmt = select(ApplicationPackageRecord).order_by(ApplicationPackageRecord.created_at.desc())
        if status:
            stmt = stmt.where(ApplicationPackageRecord.status == status)
        stmt = stmt.offset(offset).limit(limit)
        records = self._session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in records]

    def _to_domain(self, record: ApplicationPackageRecord) -> ApplicationPackage:
        return ApplicationPackage(
            id=record.id,
            recommendation_id=record.recommendation_id,
            job_id=record.job_id,
            profile_id=record.profile_id,
            final_score=record.final_score,
            status=ApprovalState(record.status),
            priority=record.priority,
            revision_number=record.revision_number,
            telegram_message_id=record.telegram_message_id,
            snapshot_json=record.snapshot_json,
            documents_json=record.documents_json,
            application_hash=record.application_hash,
            profile_version=record.profile_version,
            template_name=record.template_name,
            theme_name=record.theme_name,
            created_at=record.created_at.isoformat() if record.created_at else "",
            updated_at=record.updated_at.isoformat() if record.updated_at else "",
            approved_at=record.approved_at.isoformat() if record.approved_at else None,
            reviewed_at=record.reviewed_at.isoformat() if record.reviewed_at else None,
        )


class ApprovalQueueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self, package_id: int, score: float = 0.0, deadline: datetime | None = None
    ) -> None:
        record = ApprovalQueueRecord(package_id=package_id, score=score, deadline=deadline)
        self._session.add(record)
        self._session.flush()

    def dequeue(self, package_id: int) -> None:
        stmt = delete(ApprovalQueueRecord).where(ApprovalQueueRecord.package_id == package_id)
        self._session.execute(stmt)
        self._session.flush()

    def get_by_package_id(self, package_id: int) -> ApprovalQueueRecord | None:
        stmt = select(ApprovalQueueRecord).where(ApprovalQueueRecord.package_id == package_id)
        return self._session.execute(stmt).scalar_one_or_none()


class ApprovalEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, event: ApprovalEvent) -> ApprovalEvent:
        record = ApprovalEventRecord(
            package_id=event.package_id,
            action=event.action.value,
            actor=event.actor,
            comment=event.comment,
            previous_state=event.previous_state.value if event.previous_state else None,
            new_state=event.new_state.value if event.new_state else None,
        )
        self._session.add(record)
        self._session.flush()
        return ApprovalEvent(
            id=record.id,
            package_id=record.package_id,
            action=ApprovalAction(record.action),
            actor=record.actor,
            comment=record.comment or "",
            previous_state=ApprovalState(record.previous_state) if record.previous_state else None,
            new_state=ApprovalState(record.new_state) if record.new_state else None,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )

    def list_for_package(self, package_id: int) -> list[ApprovalEvent]:
        stmt = (
            select(ApprovalEventRecord)
            .where(ApprovalEventRecord.package_id == package_id)
            .order_by(ApprovalEventRecord.created_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [
            ApprovalEvent(
                id=r.id,
                package_id=r.package_id,
                action=ApprovalAction(r.action),
                actor=r.actor,
                comment=r.comment or "",
                previous_state=ApprovalState(r.previous_state) if r.previous_state else None,
                new_state=ApprovalState(r.new_state) if r.new_state else None,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ]


class ApprovalCommentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, comment: ApprovalComment) -> ApprovalComment:
        record = ApprovalCommentRecord(
            package_id=comment.package_id,
            author=comment.author,
            text=comment.text,
        )
        self._session.add(record)
        self._session.flush()
        return ApprovalComment(
            id=record.id,
            package_id=record.package_id,
            author=record.author,
            text=record.text,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )

    def list_for_package(self, package_id: int) -> list[ApprovalComment]:
        stmt = (
            select(ApprovalCommentRecord)
            .where(ApprovalCommentRecord.package_id == package_id)
            .order_by(ApprovalCommentRecord.created_at.asc())
        )
        records = self._session.execute(stmt).scalars().all()
        return [
            ApprovalComment(
                id=r.id,
                package_id=r.package_id,
                author=r.author,
                text=r.text,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in records
        ]
