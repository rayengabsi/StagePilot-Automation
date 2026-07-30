from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.database_url = "sqlite:///:memory:"
    s.log_level = "DEBUG"
    s.log_file = None
    return s


@pytest.fixture
def fake_resume(tmp_path: Path) -> Path:
    path = tmp_path / "resume.md"
    path.write_text(
        "John Doe\njohn@example.com\n\nEducation\nUniversity A\n\nSkills\nPython\n",
        encoding="utf-8",
    )
    return path


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
@patch("app.cli.commands.detect_parser")
def test_profile_import_success(
    mock_detect: MagicMock,
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    fake_resume: Path,
) -> None:
    from app.cli.commands import run_cli

    mock_svc = MagicMock()
    mock_profile = MagicMock()
    mock_profile.personal_info.full_name = "John Doe"
    mock_profile.education = ()
    mock_profile.experience = ()
    mock_profile.skills = ()
    mock_profile.projects = ()
    mock_profile.languages = ()
    mock_profile.certifications = ()
    mock_svc.import_resume.return_value = mock_profile
    mock_svc.get_completeness.return_value = MagicMock(score=75.0, breakdown={}, missing_fields=())
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    exit_code = run_cli(["profile", "import", str(fake_resume)])
    assert exit_code == 0
    mock_svc.import_resume.assert_called_once()


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_import_file_not_found(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_import

    args = MagicMock()
    args.file = "/nonexistent/file.pdf"
    args.description = None
    result = _handle_profile_import(args, settings)
    assert result == 1


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_show_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_show

    mock_profile = MagicMock()
    mock_profile.to_dict.return_value = {"personal_info": {"full_name": "John"}}
    mock_svc = MagicMock()
    mock_svc.get_current_profile.return_value = mock_profile
    mock_svc.get_completeness.return_value = MagicMock(score=80.0, breakdown={}, missing_fields=())
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    result = _handle_profile_show(MagicMock(), settings)
    assert result == 0


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_list_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_list

    mock_svc = MagicMock()
    mock_svc.list_profiles.return_value = (
        {"id": 1, "name": "Test", "active": True, "full_name": "John", "email": "j@x.com"},
    )
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    result = _handle_profile_list(MagicMock(), settings)
    assert result == 0


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_export_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_export

    mock_svc = MagicMock()
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    args = MagicMock()
    args.output = "test_export.json"
    result = _handle_profile_export(args, settings)
    assert result == 0
    mock_svc.export_profile.assert_called_once()


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_validate_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_validate

    mock_svc = MagicMock()
    mock_svc.validate_profile.return_value = []
    mock_svc.get_completeness.return_value = MagicMock(score=100.0, breakdown={}, missing_fields=())
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    result = _handle_profile_validate(MagicMock(), settings)
    assert result == 0


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_activate_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_activate

    mock_svc = MagicMock()
    mock_svc.activate_profile.return_value = "Test Profile"
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    args = MagicMock()
    args.profile_id = 1
    result = _handle_profile_activate(args, settings)
    assert result == 0
    mock_svc.activate_profile.assert_called_once_with(1)


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_activate_not_found(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_activate
    from app.domain.master_profile.errors import ProfileNotFoundError

    mock_svc = MagicMock()
    mock_svc.activate_profile.side_effect = ProfileNotFoundError("not found")
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    args = MagicMock()
    args.profile_id = 999
    result = _handle_profile_activate(args, settings)
    assert result == 0  # handler catches exception and prints error


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_delete_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_delete

    mock_svc = MagicMock()
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    args = MagicMock()
    args.profile_id = 1
    result = _handle_profile_delete(args, settings)
    assert result == 0
    mock_svc.delete_profile.assert_called_once_with(1)


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_delete_not_found(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_delete
    from app.domain.master_profile.errors import ProfileNotFoundError

    mock_svc = MagicMock()
    mock_svc.delete_profile.side_effect = ProfileNotFoundError("not found")
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    args = MagicMock()
    args.profile_id = 999
    result = _handle_profile_delete(args, settings)
    assert result == 0  # handler catches exception and prints error


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_edit_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_edit

    mock_svc = MagicMock()
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    args = MagicMock()
    args.profile_id = 1
    args.name = "Renamed"
    args.summary = None
    result = _handle_profile_edit(args, settings)
    assert result == 0
    mock_svc.edit_profile.assert_called_once_with(profile_id=1, name="Renamed", summary=None)


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.ProfileService")
def test_profile_versions_success(
    mock_svc_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
    settings: MagicMock,
) -> None:
    from app.cli.commands import _handle_profile_versions

    mock_version = MagicMock()
    mock_version.version_number = 1
    mock_version.completeness_score = 80.0
    mock_version.change_description = "Initial import"
    mock_version.created_at = "2024-01-01T00:00:00"
    mock_version.profile.personal_info.full_name = "John"

    mock_svc = MagicMock()
    mock_svc.list_versions.return_value = (mock_version,)
    mock_svc_cls.return_value = mock_svc
    mock_scope.return_value.__enter__.return_value = MagicMock()
    mock_scope.return_value.__exit__.return_value = None

    result = _handle_profile_versions(MagicMock(), settings)
    assert result == 0
