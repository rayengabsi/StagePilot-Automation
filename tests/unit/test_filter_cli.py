from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.cli.commands import run_cli
from app.domain.job_filters.entities import JobFilterRules


def _scope_mock(*_args: object, **_kwargs: object) -> MagicMock:
    scope = MagicMock()
    scope.__enter__.return_value = MagicMock()
    return scope


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.load_job_filter_rules")
def test_filter_show_prints_current_rules(
    mock_load: MagicMock,
    mock_scope: MagicMock,
    _mock_factory: MagicMock,
    _mock_engine: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Filter show prints the persisted rules as JSON."""
    mock_load.return_value = JobFilterRules(excluded_companies=["acme"])
    mock_scope.side_effect = _scope_mock

    exit_code = run_cli(["filter", "show"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert '"excluded_companies"' in out
    assert "acme" in out


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.save_job_filter_rules")
@patch("app.cli.commands.load_job_filter_rules")
def test_filter_set_parses_rules_json(
    mock_load: MagicMock,
    mock_save: MagicMock,
    mock_scope: MagicMock,
    _mock_factory: MagicMock,
    _mock_engine: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Filter set --rules persists a validated full rules JSON."""
    mock_load.return_value = JobFilterRules()
    mock_scope.side_effect = _scope_mock

    exit_code = run_cli(["filter", "set", "--rules", '{"required_titles": ["engineer"]}'])

    assert exit_code == 0
    rules = mock_save.call_args.args[1]
    assert isinstance(rules, JobFilterRules)
    assert rules.required_titles == ["engineer"]
    out = capsys.readouterr().out
    assert '"required_titles"' in out


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.save_job_filter_rules")
@patch("app.cli.commands.load_job_filter_rules")
def test_filter_set_parses_csv_flags(
    mock_load: MagicMock,
    mock_save: MagicMock,
    mock_scope: MagicMock,
    _mock_factory: MagicMock,
    _mock_engine: MagicMock,
) -> None:
    """Filter set merges individual CSV flags over the current rules."""
    mock_load.return_value = JobFilterRules()
    mock_scope.side_effect = _scope_mock

    exit_code = run_cli(
        [
            "filter",
            "set",
            "--excluded-companies",
            "Acme,Globex",
            "--max-job-age-days",
            "30",
            "--remote-only",
        ]
    )

    assert exit_code == 0
    rules = mock_save.call_args.args[1]
    assert rules.excluded_companies == ["Acme", "Globex"]
    assert rules.max_job_age_days == 30
    assert rules.remote_only is True


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.save_job_filter_rules")
@patch("app.cli.commands.load_job_filter_rules")
def test_filter_set_invalid_json_returns_error(
    mock_load: MagicMock,
    _mock_save: MagicMock,
    mock_scope: MagicMock,
    _mock_factory: MagicMock,
    _mock_engine: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Filter set with malformed rules JSON exits non-zero with an error."""
    mock_load.return_value = JobFilterRules()
    mock_scope.side_effect = _scope_mock

    exit_code = run_cli(["filter", "set", "--rules", "{not json"])

    assert exit_code == 1
    assert "invalid --rules JSON" in capsys.readouterr().out


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.save_job_filter_rules")
@patch("app.cli.commands.load_job_filter_rules")
def test_filter_reset_persists_empty_rules(
    mock_load: MagicMock,
    mock_save: MagicMock,
    mock_scope: MagicMock,
    _mock_factory: MagicMock,
    _mock_engine: MagicMock,
) -> None:
    """Filter reset clears every rule back to an unrestricted config."""
    mock_load.return_value = JobFilterRules()
    mock_scope.side_effect = _scope_mock

    exit_code = run_cli(["filter", "reset"])

    assert exit_code == 0
    rules = mock_save.call_args.args[1]
    assert rules.is_empty()


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.UserFilterService")
def test_filter_test_prints_decision(
    mock_service_cls: MagicMock,
    mock_scope: MagicMock,
    _mock_factory: MagicMock,
    _mock_engine: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Filter test evaluates one job and prints an explainable decision."""
    job = MagicMock()
    job.id = 7
    job.title = "Senior Engineer"
    job.company = "Acme"
    job.location = "Tunis"
    result = MagicMock()
    result.passed = False
    rejection = MagicMock()
    rejection.code.value = "excluded_title"
    rejection.detail = "Title contains an excluded term."
    rejection.matched_value = "senior"
    result.rejections = [rejection]
    mock_service = MagicMock()
    mock_service.evaluate.return_value = result
    mock_service_cls.return_value = mock_service

    session = MagicMock()
    session.get.return_value = job
    scope = MagicMock()
    scope.__enter__.return_value = session
    mock_scope.side_effect = lambda *_a, **_k: scope

    exit_code = run_cli(["filter", "test", "--job-id", "7"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "excluded_title" in out
    assert "Title contains an excluded term." in out
