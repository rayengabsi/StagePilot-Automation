from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.repositories.approval import (
    ApplicationPackageRepository,
    ApprovalCommentRepository,
    ApprovalEventRepository,
    ApprovalQueueRepository,
)
from app.domain.approval.entities import ApplicationPackage, ApprovalComment, ApprovalEvent
from app.domain.approval.enums import (
    ApprovalAction,
    ApprovalState,
    QueueStrategy,
    is_valid_transition,
)
from app.domain.approval.errors import (
    DocumentNotFoundError,
    DuplicateApprovalError,
    InvalidTransitionError,
)
from app.services.queue_service import QueueService
from app.services.snapshot_service import SnapshotService


class ApprovalService:
    """Owns ALL approval business logic. UI-independent.

    Responsibilities:
        - Queue management (enqueue, dequeue, list)
        - State transitions with validation
        - Audit logging
        - Snapshot creation and retrieval
        - Document retrieval
        - History
    """

    def __init__(
        self,
        session: Session,
        queue_strategy: QueueStrategy = QueueStrategy.FIFO,
        queue_limit: int = 50,
    ) -> None:
        self._session = session
        self._package_repo = ApplicationPackageRepository(session)
        self._event_repo = ApprovalEventRepository(session)
        self._comment_repo = ApprovalCommentRepository(session)
        self._queue_repo = ApprovalQueueRepository(session)
        self._queue_service = QueueService(session, queue_strategy, queue_limit)
        self._snapshot_service = SnapshotService()

    # ── Package management ──────────────────────────────────────────

    def create_package(self, package: ApplicationPackage) -> ApplicationPackage:
        saved = self._package_repo.save(package)
        self._record_event(
            package_id=saved.id,
            action=ApprovalAction.QUEUED,
            actor="system",
            comment="Application package created",
        )
        return saved

    def get_package(self, package_id: int) -> ApplicationPackage:
        return self._package_repo.get_by_id(package_id)

    def list_packages(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ApplicationPackage]:
        return self._package_repo.list_all(status=status, limit=limit, offset=offset)

    # ── Queue operations ────────────────────────────────────────────

    def enqueue(self, package_id: int, score: float = 0.0) -> ApplicationPackage:
        package = self._package_repo.get_by_id(package_id)
        self._validate_transition(package.status, ApprovalState.QUEUED)
        updated = self._queue_service.enqueue(package, score=score)
        self._record_event(
            package_id=package_id,
            action=ApprovalAction.QUEUED,
            actor="system",
            previous_state=package.status,
            new_state=ApprovalState.QUEUED,
            comment="Package added to approval queue",
        )
        return updated

    def dequeue(self, package_id: int) -> None:
        self._queue_service.dequeue(package_id)

    def peek_queue(self, limit: int = 10, offset: int = 0) -> list[ApplicationPackage]:
        return self._queue_service.peek(limit=limit, offset=offset)

    def queue_count(self) -> int:
        return self._queue_service.count()

    # ── State transitions ───────────────────────────────────────────

    def approve(self, package_id: int, actor: str, comment: str = "") -> ApplicationPackage:
        package = self._package_repo.get_by_id(package_id)
        if package.status == ApprovalState.APPROVED:
            msg = f"Package {package_id} already approved"
            raise DuplicateApprovalError(msg)
        self._validate_transition(package.status, ApprovalState.APPROVED)
        self._package_repo.update_status(package_id, ApprovalState.APPROVED)
        self._queue_repo.dequeue(package_id)
        self._record_event(
            package_id=package_id,
            action=ApprovalAction.APPROVED,
            actor=actor,
            previous_state=package.status,
            new_state=ApprovalState.APPROVED,
            comment=comment,
        )
        return self._package_repo.get_by_id(package_id)

    def reject(self, package_id: int, actor: str, comment: str = "") -> ApplicationPackage:
        package = self._package_repo.get_by_id(package_id)
        self._validate_transition(package.status, ApprovalState.REJECTED)
        self._package_repo.update_status(package_id, ApprovalState.REJECTED)
        self._queue_repo.dequeue(package_id)
        self._record_event(
            package_id=package_id,
            action=ApprovalAction.REJECTED,
            actor=actor,
            previous_state=package.status,
            new_state=ApprovalState.REJECTED,
            comment=comment,
        )
        return self._package_repo.get_by_id(package_id)

    def request_revision(
        self, package_id: int, actor: str, comment: str = ""
    ) -> ApplicationPackage:
        package = self._package_repo.get_by_id(package_id)
        self._validate_transition(package.status, ApprovalState.REVISION_REQUESTED)
        self._package_repo.update_status(package_id, ApprovalState.REVISION_REQUESTED)
        self._queue_repo.dequeue(package_id)
        self._record_event(
            package_id=package_id,
            action=ApprovalAction.REVISION_REQUESTED,
            actor=actor,
            previous_state=package.status,
            new_state=ApprovalState.REVISION_REQUESTED,
            comment=comment,
        )
        return self._package_repo.get_by_id(package_id)

    def skip(self, package_id: int, actor: str, comment: str = "") -> ApplicationPackage:
        package = self._package_repo.get_by_id(package_id)
        self._validate_transition(package.status, ApprovalState.SKIPPED)
        self._package_repo.update_status(package_id, ApprovalState.SKIPPED)
        self._queue_repo.dequeue(package_id)
        self._record_event(
            package_id=package_id,
            action=ApprovalAction.SKIPPED,
            actor=actor,
            previous_state=package.status,
            new_state=ApprovalState.SKIPPED,
            comment=comment,
        )
        return self._package_repo.get_by_id(package_id)

    def archive(self, package_id: int, actor: str, comment: str = "") -> ApplicationPackage:
        package = self._package_repo.get_by_id(package_id)
        self._validate_transition(package.status, ApprovalState.ARCHIVED)
        self._package_repo.update_status(package_id, ApprovalState.ARCHIVED)
        self._queue_repo.dequeue(package_id)
        self._record_event(
            package_id=package_id,
            action=ApprovalAction.ARCHIVED,
            actor=actor,
            previous_state=package.status,
            new_state=ApprovalState.ARCHIVED,
            comment=comment,
        )
        return self._package_repo.get_by_id(package_id)

    def start_review(self, package_id: int, actor: str) -> ApplicationPackage:
        package = self._package_repo.get_by_id(package_id)
        self._validate_transition(package.status, ApprovalState.UNDER_REVIEW)
        self._package_repo.update_status(package_id, ApprovalState.UNDER_REVIEW)
        self._record_event(
            package_id=package_id,
            action=ApprovalAction.VIEWED,
            actor=actor,
            previous_state=package.status,
            new_state=ApprovalState.UNDER_REVIEW,
            comment="Review started",
        )
        return self._package_repo.get_by_id(package_id)

    # ── Document retrieval ──────────────────────────────────────────

    def get_documents(self, package_id: int) -> dict[str, str]:
        import json

        package = self._package_repo.get_by_id(package_id)
        try:
            return dict(json.loads(package.documents_json))
        except (json.JSONDecodeError, TypeError) as exc:
            msg = f"Invalid documents_json for package {package_id}"
            raise DocumentNotFoundError(msg) from exc

    def get_snapshot(self, package_id: int) -> dict[str, Any]:
        import json

        package = self._package_repo.get_by_id(package_id)
        try:
            return dict(json.loads(package.snapshot_json))
        except (json.JSONDecodeError, TypeError) as exc:
            msg = f"Invalid snapshot_json for package {package_id}"
            raise DocumentNotFoundError(msg) from exc

    # ── History ─────────────────────────────────────────────────────

    def get_history(self, package_id: int) -> list[ApprovalEvent]:
        return self._event_repo.list_for_package(package_id)

    def get_comments(self, package_id: int) -> list[ApprovalComment]:
        return self._comment_repo.list_for_package(package_id)

    def add_comment(self, package_id: int, author: str, text: str) -> ApprovalComment:
        comment = ApprovalComment(package_id=package_id, author=author, text=text)
        return self._comment_repo.add(comment)

    # ── Internal helpers ────────────────────────────────────────────

    def _validate_transition(self, from_state: ApprovalState, to_state: ApprovalState) -> None:
        if not is_valid_transition(from_state, to_state):
            msg = f"Invalid transition: {from_state.value} -> {to_state.value}"
            raise InvalidTransitionError(msg)

    def _record_event(
        self,
        package_id: int,
        action: ApprovalAction,
        actor: str,
        previous_state: ApprovalState | None = None,
        new_state: ApprovalState | None = None,
        comment: str = "",
    ) -> None:
        event = ApprovalEvent(
            package_id=package_id,
            action=action,
            actor=actor,
            comment=comment,
            previous_state=previous_state,
            new_state=new_state,
        )
        self._event_repo.record(event)
