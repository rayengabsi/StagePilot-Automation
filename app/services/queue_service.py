from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, nullslast, select
from sqlalchemy.orm import Session

from app.db.models.approval import ApplicationPackageRecord, ApprovalQueueRecord
from app.db.repositories.approval import ApplicationPackageRepository, ApprovalQueueRepository
from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.enums import ApprovalState, QueueStrategy
from app.domain.approval.errors import QueueFullError


class QueueService:
    """Manages the approval queue with multiple strategies."""

    def __init__(
        self,
        session: Session,
        strategy: QueueStrategy = QueueStrategy.FIFO,
        queue_limit: int = 50,
    ) -> None:
        self._session = session
        self._strategy = strategy
        self._queue_limit = queue_limit
        self._package_repo = ApplicationPackageRepository(session)
        self._queue_repo = ApprovalQueueRepository(session)

    def enqueue(
        self,
        package: ApplicationPackage,
        score: float = 0.0,
        deadline: datetime | None = None,
    ) -> ApplicationPackage:
        current_count = self._get_queue_count()
        if current_count >= self._queue_limit:
            msg = f"Queue limit of {self._queue_limit} reached"
            raise QueueFullError(msg)

        self._package_repo.update_status(package.id, ApprovalState.QUEUED)
        self._queue_repo.enqueue(package.id, score=score, deadline=deadline)
        return self._package_repo.get_by_id(package.id)

    def dequeue(self, package_id: int) -> None:
        self._queue_repo.dequeue(package_id)

    def peek(self, limit: int = 10, offset: int = 0) -> list[ApplicationPackage]:
        strategy_order = self._build_order_clause()
        stmt = (
            select(ApplicationPackageRecord)
            .join(
                ApprovalQueueRecord,
                ApplicationPackageRecord.id == ApprovalQueueRecord.package_id,
            )
            .where(ApplicationPackageRecord.status.in_(["queued", "under_review"]))
            .order_by(strategy_order)
            .offset(offset)
            .limit(limit)
        )
        records = self._session.execute(stmt).scalars().all()
        return [self._package_repo._to_domain(r) for r in records]

    def count(self) -> int:
        return self._get_queue_count()

    def _get_queue_count(self) -> int:
        stmt = select(ApprovalQueueRecord)
        return len(self._session.execute(stmt).scalars().all())

    def _build_order_clause(self) -> Any:  # noqa: ANN401
        if self._strategy == QueueStrategy.FIFO:
            return asc(ApprovalQueueRecord.created_at)
        if self._strategy == QueueStrategy.HIGHEST_SCORE:
            return desc(ApprovalQueueRecord.score)
        if self._strategy == QueueStrategy.DEADLINE_PRIORITY:
            return nullslast(asc(ApprovalQueueRecord.deadline))
        if self._strategy == QueueStrategy.NEWEST_FIRST:
            return desc(ApprovalQueueRecord.created_at)
        if self._strategy == QueueStrategy.OLDEST_FIRST:
            return asc(ApprovalQueueRecord.created_at)
        return asc(ApprovalQueueRecord.created_at)
