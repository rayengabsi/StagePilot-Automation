from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.cli.commands import _build_company_config, _handle_add_provider_source, run_cli
from app.domain.jobs.enums import JobSourceType


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.JobSourceRepository")
def test_add_provider_source_uses_generic_add(
    mock_repo_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
) -> None:
    """Sources add-greenhouse should add a greenhouse source."""
    mock_repo = MagicMock()
    mock_source = MagicMock()
    mock_source.id = 3
    mock_source.name = "Acme"
    mock_source.type = "greenhouse"
    mock_source.base_url = "https://boards.greenhouse.io/acme"
    mock_source.config_json = {"token": "acme"}
    mock_repo.add_source.return_value = mock_source
    mock_repo_cls.return_value = mock_repo
    mock_scope.return_value.__enter__.return_value = MagicMock()

    exit_code = run_cli(
        [
            "sources",
            "add-greenhouse",
            "--name",
            "Acme",
            "--url",
            "https://boards.greenhouse.io/acme",
            "--token",
            "acme",
        ]
    )

    assert exit_code == 0
    mock_repo.add_source.assert_called_once()
    _, kwargs = mock_repo.add_source.call_args
    assert kwargs["source_type"] == JobSourceType.GREENHOUSE
    assert kwargs["config"] == {"token": "acme"}


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.JobSourceRepository")
def test_add_company_source_builds_selector_config(
    mock_repo_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
) -> None:
    """Sources add-company should persist a company_pages config."""
    mock_repo = MagicMock()
    mock_source = MagicMock()
    mock_source.id = 9
    mock_source.name = "Acme Careers"
    mock_source.type = "company_pages"
    mock_source.base_url = "https://acme.com/careers"
    mock_source.config_json = {"job_links_selector": "a.job"}
    mock_repo.add_source.return_value = mock_source
    mock_repo_cls.return_value = mock_repo
    mock_scope.return_value.__enter__.return_value = MagicMock()

    exit_code = run_cli(
        [
            "sources",
            "add-company",
            "--name",
            "Acme Careers",
            "--url",
            "https://acme.com/careers",
            "--selector",
            "a.job",
        ]
    )

    assert exit_code == 0
    _, kwargs = mock_repo.add_source.call_args
    assert kwargs["source_type"] == JobSourceType.COMPANY_PAGES
    assert kwargs["config"]["job_links_selector"] == "a.job"


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.JobSourceRepository")
def test_remove_source_calls_repo(
    mock_repo_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
) -> None:
    """Sources remove --id should delete the source."""
    mock_repo = MagicMock()
    mock_repo.remove_source.return_value = True
    mock_repo_cls.return_value = mock_repo
    mock_scope.return_value.__enter__.return_value = MagicMock()

    exit_code = run_cli(["sources", "remove", "--id", "5"])

    assert exit_code == 0
    mock_repo.remove_source.assert_called_once_with(5)


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.JobSourceRepository")
def test_set_source_active_flags(
    mock_repo_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
) -> None:
    """Sources enable/disable should toggle the active flag."""
    mock_repo = MagicMock()
    mock_source = MagicMock()
    mock_source.id = 2
    mock_source.name = "Feed"
    mock_source.is_active = False
    mock_repo.set_source_active.return_value = mock_source
    mock_repo_cls.return_value = mock_repo
    mock_scope.return_value.__enter__.return_value = MagicMock()

    exit_code = run_cli(["sources", "disable", "--id", "2"])

    assert exit_code == 0
    mock_repo.set_source_active.assert_called_once_with(2, False)


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.JobSourceRepository")
@patch("app.cli.commands.build_connector_registry")
def test_source_health_reports_healthy(
    mock_registry: MagicMock,
    mock_repo_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
) -> None:
    """Sources health should surface the connector health result."""
    mock_repo = MagicMock()
    record = MagicMock()
    record.id = 1
    record.name = "Acme"
    record.type = "greenhouse"
    record.base_url = "https://boards.greenhouse.io/acme"
    record.config_json = {"token": "acme"}
    mock_repo.get_source.return_value = record
    mock_repo_cls.return_value = mock_repo

    mock_connector = MagicMock()
    health = MagicMock()
    health.provider = "greenhouse"
    health.status = "healthy"
    health.latency_ms = 12.5
    health.message = "OK"
    mock_connector.health.return_value = health
    mock_registry.return_value.get.return_value = mock_connector
    mock_scope.return_value.__enter__.return_value = MagicMock()

    exit_code = run_cli(["sources", "health", "--id", "1"])

    assert exit_code == 0
    mock_registry.return_value.get.assert_called_once()
    assert mock_registry.return_value.get.call_args[0][0] == JobSourceType.GREENHOUSE


@patch("app.cli.commands.create_database_engine")
@patch("app.cli.commands.create_session_factory")
@patch("app.cli.commands.session_scope")
@patch("app.cli.commands.JobSourceRepository")
@patch("app.cli.commands.build_connector_registry")
def test_source_test_validates_and_fetches(
    mock_registry: MagicMock,
    mock_repo_cls: MagicMock,
    mock_scope: MagicMock,
    mock_factory: MagicMock,
    mock_engine: MagicMock,
) -> None:
    """Sources test should validate config and dry-run fetch."""
    mock_repo = MagicMock()
    record = MagicMock()
    record.id = 1
    record.name = "Acme"
    record.type = "lever"
    record.base_url = "https://jobs.lever.co/acme"
    record.config_json = {"company": "acme"}
    mock_repo.get_source.return_value = record
    mock_repo_cls.return_value = mock_repo

    mock_connector = MagicMock()
    mock_connector.provider_name_value.return_value = "lever"
    mock_connector.validate.return_value = []
    job = MagicMock()
    job.title = "Engineer"
    mock_connector.fetch.return_value = [job]
    mock_registry.return_value.get.return_value = mock_connector
    mock_scope.return_value.__enter__.return_value = MagicMock()

    exit_code = run_cli(["sources", "test", "--id", "1"])

    assert exit_code == 0
    mock_connector.validate.assert_called_once()
    mock_connector.fetch.assert_called_once()


def test_build_company_config_defaults() -> None:
    """Company config should default max_pages and scrape_details."""
    args = MagicMock()
    args.selector = "a.job"
    args.list_url = None
    args.next_selector = None
    args.title_selector = None
    args.description_selector = None
    args.max_pages = 1
    args.no_scrape_details = False
    args.company = "Acme"

    config = _build_company_config(args)

    assert config["job_links_selector"] == "a.job"
    assert config["scrape_details"] is True
    assert config["max_pages"] == 1
    assert config["company"] == "Acme"


def test_handle_add_provider_source_rejects_unknown_provider() -> None:
    """Unknown provider names should raise KeyError."""
    import pytest

    args = MagicMock()
    args.name = "X"
    args.url = "https://example.com"

    with pytest.raises(KeyError):
        _handle_add_provider_source(args, MagicMock(), "unknown_provider", {})
