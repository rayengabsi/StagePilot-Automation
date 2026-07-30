from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.db.repositories.approval import (
    ApplicationPackageRepository,
    ApprovalEventRepository,
    ApprovalQueueRepository,
)
from app.domain.approval.entities import ApplicationPackage, ApprovalEvent
from app.domain.approval.enums import ApprovalAction, ApprovalState
from app.domain.approval.errors import (
    DuplicateApprovalError,
    InvalidTransitionError,
    PackageNotFoundError,
)
from app.services.approval_service import ApprovalService


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_package() -> ApplicationPackage:
    return ApplicationPackage(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        final_score=85.0,
        snapshot_json='{"recommendation": {"job": {"company": "Acme"}}}',
        documents_json='{"resume_pdf": "resume.pdf"}',
        application_hash="abc",
        status=ApprovalState.NEW,
        profile_version="current",
        template_name="modern",
        theme_name="default",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_create_package(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
    mock_package: ApplicationPackage,
) -> None:
    instance = MagicMock()
    instance.save.return_value = mock_package
    mock_p_repo.return_value = instance

    svc = ApprovalService(session=mock_session)
    svc._package_repo = instance
    svc._event_repo = mock_e_repo.return_value

    result = svc.create_package(mock_package)
    assert result.id == 1
    assert result.final_score == 85.0
    instance.save.assert_called_once_with(mock_package)


@patch("app.db.repositories.approval.ApplicationPackageRepository")
def test_get_package_not_found(mock_p_repo: MagicMock, mock_session: MagicMock) -> None:
    instance = MagicMock()
    instance.get_by_id.side_effect = PackageNotFoundError("not found")
    mock_p_repo.return_value = instance

    svc = ApprovalService(session=mock_session)
    svc._package_repo = instance

    with pytest.raises(PackageNotFoundError):
        svc.get_package(999)


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_approve_package(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash1",
        status=ApprovalState.UNDER_REVIEW,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    approved_pkg = ApplicationPackage(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash1",
        status=ApprovalState.APPROVED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.side_effect = [pkg, approved_pkg]
    e_repo = MagicMock(spec=ApprovalEventRepository)
    q_repo = MagicMock(spec=ApprovalQueueRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = q_repo

    result = svc.approve(package_id=1, actor="test_user", comment="Looks good!")
    assert result.status == ApprovalState.APPROVED
    p_repo.update_status.assert_called_once_with(1, ApprovalState.APPROVED)
    q_repo.dequeue.assert_called_once_with(1)
    e_repo.record.assert_called_once()


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_duplicate_approval_raises_error(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash1",
        status=ApprovalState.APPROVED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.return_value = pkg
    e_repo = MagicMock(spec=ApprovalEventRepository)
    q_repo = MagicMock(spec=ApprovalQueueRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = q_repo

    with pytest.raises(DuplicateApprovalError):
        svc.approve(package_id=1, actor="tester")


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_invalid_transition_raises_error(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash1",
        status=ApprovalState.NEW,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.return_value = pkg
    e_repo = MagicMock(spec=ApprovalEventRepository)
    q_repo = MagicMock(spec=ApprovalQueueRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = q_repo

    with pytest.raises(InvalidTransitionError):
        svc.approve(package_id=1, actor="tester")


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_reject_package(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=2,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash2",
        status=ApprovalState.UNDER_REVIEW,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    rejected = ApplicationPackage(
        id=2,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash2",
        status=ApprovalState.REJECTED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.side_effect = [pkg, rejected]
    e_repo = MagicMock(spec=ApprovalEventRepository)
    q_repo = MagicMock(spec=ApprovalQueueRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = q_repo

    result = svc.reject(package_id=2, actor="test_user", comment="Not a fit")
    assert result.status == ApprovalState.REJECTED


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_request_revision(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=3,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash3",
        status=ApprovalState.UNDER_REVIEW,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    revised = ApplicationPackage(
        id=3,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash3",
        status=ApprovalState.REVISION_REQUESTED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.side_effect = [pkg, revised]
    e_repo = MagicMock(spec=ApprovalEventRepository)
    q_repo = MagicMock(spec=ApprovalQueueRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = q_repo

    result = svc.request_revision(package_id=3, actor="test_user", comment="Please update")
    assert result.status == ApprovalState.REVISION_REQUESTED


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_skip_package(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=4,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash4",
        status=ApprovalState.QUEUED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    skipped = ApplicationPackage(
        id=4,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash4",
        status=ApprovalState.SKIPPED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.side_effect = [pkg, skipped]
    e_repo = MagicMock(spec=ApprovalEventRepository)
    q_repo = MagicMock(spec=ApprovalQueueRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = q_repo

    result = svc.skip(package_id=4, actor="test_user")
    assert result.status == ApprovalState.SKIPPED


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_archive_package(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=5,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash5",
        status=ApprovalState.APPROVED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    archived = ApplicationPackage(
        id=5,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash5",
        status=ApprovalState.ARCHIVED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.side_effect = [pkg, archived]
    e_repo = MagicMock(spec=ApprovalEventRepository)
    q_repo = MagicMock(spec=ApprovalQueueRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = q_repo

    result = svc.archive(package_id=5, actor="test_user")
    assert result.status == ApprovalState.ARCHIVED


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
def test_start_review(
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    pkg = ApplicationPackage(
        id=6,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash6",
        status=ApprovalState.QUEUED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    reviewed = ApplicationPackage(
        id=6,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="hash6",
        status=ApprovalState.UNDER_REVIEW,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.get_by_id.side_effect = [pkg, reviewed]
    e_repo = MagicMock(spec=ApprovalEventRepository)

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo
    svc._event_repo = e_repo
    svc._queue_repo = MagicMock()

    result = svc.start_review(package_id=6, actor="test_user")
    assert result.status == ApprovalState.UNDER_REVIEW


def test_get_history(mock_session: MagicMock) -> None:
    events = [
        ApprovalEvent(
            id=1,
            package_id=1,
            action=ApprovalAction.QUEUED,
            actor="system",
            created_at="2026-01-01T00:00:00",
        ),
        ApprovalEvent(
            id=2,
            package_id=1,
            action=ApprovalAction.APPROVED,
            actor="admin",
            new_state=ApprovalState.APPROVED,
            previous_state=ApprovalState.UNDER_REVIEW,
            created_at="2026-01-02T00:00:00",
        ),
    ]
    e_repo = MagicMock(spec=ApprovalEventRepository)
    e_repo.list_for_package.return_value = events
    svc = ApprovalService(session=mock_session)
    svc._event_repo = e_repo

    result = svc.get_history(1)
    assert len(result) == 2
    assert result[0].action == ApprovalAction.QUEUED
    assert result[1].action == ApprovalAction.APPROVED


@patch("app.db.repositories.approval.ApplicationPackageRepository")
@patch("app.db.repositories.approval.ApprovalEventRepository")
@patch("app.db.repositories.approval.ApprovalQueueRepository")
def test_list_packages(
    mock_q_repo: MagicMock,
    mock_e_repo: MagicMock,
    mock_p_repo: MagicMock,
    mock_session: MagicMock,
) -> None:
    packages = [
        ApplicationPackage(
            id=i,
            recommendation_id=1,
            job_id=1,
            profile_id=1,
            final_score=float(i * 10),
            snapshot_json="{}",
            documents_json="{}",
            application_hash=f"hash{i}",
            status=ApprovalState.NEW,
            profile_version="v1",
            template_name="modern",
            theme_name="default",
        )
        for i in range(3)
    ]
    p_repo = MagicMock(spec=ApplicationPackageRepository)
    p_repo.list_all.return_value = packages

    svc = ApprovalService(session=mock_session)
    svc._package_repo = p_repo

    result = svc.list_packages()
    assert len(result) == 3
    p_repo.list_all.assert_called_once_with(status=None, limit=50, offset=0)
