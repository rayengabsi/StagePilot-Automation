from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, patch

import pytest
from app.domain.applications.entities import JobApplication
from app.domain.applications.enums import ApplicationState


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.database_url = "sqlite:///:memory:"
    s.log_level = "DEBUG"
    s.log_file = None
    return s


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
        status=ApplicationState.SUBMITTED,
    )


@contextmanager
def _patch_handlers() -> Iterator[tuple[MagicMock, MagicMock, MagicMock, MagicMock]]:
    with ExitStack() as stack:
        mock_engine = stack.enter_context(patch("app.cli.commands.create_database_engine"))
        mock_factory = stack.enter_context(patch("app.cli.commands.create_session_factory"))
        mock_scope = stack.enter_context(patch("app.cli.commands.session_scope"))
        mock_svc_cls = stack.enter_context(patch("app.cli.commands.ApplicationService"))
        yield mock_engine, mock_factory, mock_scope, mock_svc_cls


def test_application_list_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_list

        args = MagicMock()
        args.status = None
        args.company = None
        args.label = None
        args.date_from = None
        args.date_to = None
        args.limit = 50
        args.offset = 0

        mock_svc = MagicMock()
        mock_svc.list_applications.return_value = []
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_list(args, settings)
        assert result == 0
        mock_svc.list_applications.assert_called_once()


def test_application_show_command(settings: MagicMock, app_domain: JobApplication) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_show

        args = MagicMock()
        args.application_id = 1

        mock_svc = MagicMock()
        mock_svc.get_application.return_value = app_domain
        mock_svc.get_timeline.return_value = []
        mock_svc.get_history.return_value = []
        mock_svc.list_notes.return_value = []
        mock_svc.list_reminders.return_value = []
        mock_svc.get_outcome.return_value = None
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_show(args, settings)
        assert result == 0
        mock_svc.get_application.assert_called_once_with(1)


def test_application_update_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_update

        args = MagicMock()
        args.application_id = 1
        args.actor = "cli"
        args.company = "Acme"
        args.job_title = None
        args.resume_path = None
        args.cover_letter_path = None
        args.labels = None
        args.add_label = None
        args.remove_label = None
        args.note = None
        args.status = ApplicationState.SUBMITTED.value
        args.comment = ""

        mock_svc = MagicMock()
        mock_svc.update_application.return_value = JobApplication(
            id=1,
            recommendation_id=10,
            job_id=20,
            profile_id=30,
            profile_version="v2",
            company_name="Acme",
            job_title="Backend Engineer",
        )
        mock_svc.change_status.return_value = mock_svc.update_application.return_value
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_update(args, settings)
        assert result == 0
        mock_svc.update_application.assert_called_once()
        mock_svc.change_status.assert_called_once_with(1, "submitted", "cli", comment="")


def test_application_archive_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_archive

        args = MagicMock()
        args.application_id = 1
        args.actor = "cli"
        args.comment = "Done"

        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_archive(args, settings)
        assert result == 0
        mock_svc.archive.assert_called_once_with(1, "cli", comment="Done")


def test_application_search_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_search

        args = MagicMock()
        args.query = "Acme"
        args.limit = 20

        mock_svc = MagicMock()
        mock_svc.search_applications.return_value = []
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_search(args, settings)
        assert result == 0
        mock_svc.search_applications.assert_called_once_with("Acme", limit=20)


def test_application_summarize_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_summarize

        args = MagicMock()
        mock_svc = MagicMock()
        mock_svc.summarize.return_value = {"total": 3}
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_summarize(args, settings)
        assert result == 0
        mock_svc.summarize.assert_called_once()


def test_application_analytics_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_analytics

        args = MagicMock()
        mock_svc = MagicMock()
        mock_svc.analytics.return_value = {"total": 0}
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_analytics(args, settings)
        assert result == 0
        mock_svc.analytics.assert_called_once()


def test_application_create_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_create

        args = MagicMock()
        args.package_id = 5
        args.actor = "cli"

        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_create(args, settings)
        assert result == 0
        mock_svc.create_from_approved_package.assert_called_once_with(package_id=5, actor="cli")


def test_application_reminder_add_command(settings: MagicMock) -> None:
    with _patch_handlers() as (_mock_engine, _mock_factory, mock_scope, mock_svc_cls):
        from app.cli.commands import _handle_application_reminder_add

        args = MagicMock()
        args.application_id = 1
        args.actor = "cli"
        args.due_at = None
        args.due_days = 3
        args.message = "Follow up"

        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_svc
        mock_scope.return_value.__enter__.return_value = MagicMock()
        mock_scope.return_value.__exit__.return_value = None

        result = _handle_application_reminder_add(args, settings)
        assert result == 0
        mock_svc.schedule_follow_up.assert_called_once_with(
            1, "cli", due_at=None, due_days=3, message="Follow up"
        )
