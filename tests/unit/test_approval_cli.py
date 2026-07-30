from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.database_url = "sqlite:///:memory:"
    s.log_level = "DEBUG"
    s.log_file = None
    return s


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ApprovalService")
def test_approval_queue_command(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_approval_queue

    args = MagicMock()
    args.limit = 10
    args.offset = 0

    mock_svc = MagicMock()
    mock_svc.peek_queue.return_value = []
    mock_svc.queue_count.return_value = 0
    mock_svc_cls.return_value = mock_svc

    MagicMock()
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    result = _handle_approval_queue(args, settings)
    assert result == 0
    mock_svc.peek_queue.assert_called_once_with(limit=10, offset=0)


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ApprovalService")
def test_approval_approve_command(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_approval_approve

    args = MagicMock()
    args.package_id = 1
    args.actor = "cli-test"
    args.comment = "Looks good"

    mock_svc = MagicMock()
    from app.domain.approval.entities import ApplicationPackage
    from app.domain.approval.enums import ApprovalState

    mock_svc.approve.return_value = ApplicationPackage(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=80.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="abc",
        status=ApprovalState.APPROVED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
        approved_at="2026-01-01T00:00:00",
    )
    mock_svc_cls.return_value = mock_svc

    result = _handle_approval_approve(args, settings)
    assert result == 0
    mock_svc.approve.assert_called_once_with(package_id=1, actor="cli-test", comment="Looks good")


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ApprovalService")
def test_approval_reject_command(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_approval_reject

    args = MagicMock()
    args.package_id = 2
    args.actor = "cli-test"
    args.comment = "Not suitable"

    mock_svc = MagicMock()
    mock_svc_cls.return_value = mock_svc

    result = _handle_approval_reject(args, settings)
    assert result == 0
    mock_svc.reject.assert_called_once_with(package_id=2, actor="cli-test", comment="Not suitable")


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ApprovalService")
def test_approval_revise_command(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_approval_revise

    args = MagicMock()
    args.package_id = 3
    args.actor = "cli-test"
    args.comment = "Please update"

    mock_svc = MagicMock()
    mock_svc_cls.return_value = mock_svc

    result = _handle_approval_revise(args, settings)
    assert result == 0
    mock_svc.request_revision.assert_called_once_with(
        package_id=3, actor="cli-test", comment="Please update"
    )


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ApprovalService")
def test_approval_skip_command(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_approval_skip

    args = MagicMock()
    args.package_id = 4
    args.actor = "cli-test"

    mock_svc = MagicMock()
    mock_svc_cls.return_value = mock_svc

    result = _handle_approval_skip(args, settings)
    assert result == 0
    mock_svc.skip.assert_called_once()


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ApprovalService")
def test_approval_list_command(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_approval_list

    args = MagicMock()
    args.status = None
    args.limit = 50

    mock_svc = MagicMock()
    mock_svc.list_packages.return_value = []
    mock_svc_cls.return_value = mock_svc

    result = _handle_approval_list(args, settings)
    assert result == 0
    mock_svc.list_packages.assert_called_once()
