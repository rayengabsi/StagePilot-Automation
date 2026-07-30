from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.enums import ApprovalState, QueueStrategy
from app.domain.approval.errors import QueueFullError
from app.services.queue_service import QueueService


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def package() -> ApplicationPackage:
    return ApplicationPackage(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=85.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="abc",
        status=ApprovalState.NEW,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_enqueue(
    mock_q_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
    package: ApplicationPackage,
) -> None:
    from app.domain.approval.entities import ApplicationPackage as AP
    from app.domain.approval.enums import ApprovalState

    q_instance = MagicMock()
    p_instance = MagicMock()

    queued_pkg = AP(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=85.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="abc",
        status=ApprovalState.QUEUED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_instance.get_by_id.return_value = queued_pkg
    mock_q_repo.return_value = q_instance
    mock_p_repo.return_value = p_instance

    svc = QueueService(session=mock_session, strategy=QueueStrategy.FIFO, queue_limit=50)
    svc._queue_repo = q_instance
    svc._package_repo = p_instance

    result = svc.enqueue(package)
    assert result.status == ApprovalState.QUEUED
    p_instance.update_status.assert_called_once_with(1, ApprovalState.QUEUED)
    q_instance.enqueue.assert_called_once()


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_enqueue_full(
    mock_q_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
    package: ApplicationPackage,
) -> None:
    q_instance = MagicMock()
    p_instance = MagicMock()
    mock_q_repo.return_value = q_instance
    mock_p_repo.return_value = p_instance

    svc = QueueService(session=mock_session, strategy=QueueStrategy.FIFO, queue_limit=0)
    svc._queue_repo = q_instance
    svc._package_repo = p_instance

    with pytest.raises(QueueFullError):
        svc.enqueue(package)


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_dequeue(
    mock_q_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    q_instance = MagicMock()
    mock_q_repo.return_value = q_instance

    svc = QueueService(session=mock_session)
    svc._queue_repo = q_instance

    svc.dequeue(1)
    q_instance.dequeue.assert_called_once_with(1)


def test_strategy_enum_values() -> None:
    assert QueueStrategy.FIFO.value == "fifo"
    assert QueueStrategy.HIGHEST_SCORE.value == "highest_score"
    assert QueueStrategy.DEADLINE_PRIORITY.value == "deadline_priority"
    assert QueueStrategy.NEWEST_FIRST.value == "newest_first"
    assert QueueStrategy.OLDEST_FIRST.value == "oldest_first"
