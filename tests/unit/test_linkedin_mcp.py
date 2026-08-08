from __future__ import annotations

import pytest
from app.config.settings import get_settings
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.linkedin_mcp_connector import (
    LinkedInMCPConnector,
    _extract_job_ids,
)
from app.infrastructure.linkedin_mcp.client import (
    LinkedInMCPError,
    _maybe_json,
    _parse_call_result,
)


def _job_connector() -> LinkedInMCPConnector:
    from app.config.settings import get_settings

    return LinkedInMCPConnector(get_settings())


def _source_config(**config: object) -> JobSourceConfig:
    merged: dict[str, object] = {"tool_name": "search_jobs"}
    merged.update(config)
    return JobSourceConfig(
        id=1,
        name="linkedin",
        type=JobSourceType.LINKEDIN_MCP,
        base_url="uvx",
        config=merged,
    )


def test_provider_type_mapped() -> None:
    assert LinkedInMCPConnector.provider_name == "linkedin_mcp"
    assert LinkedInMCPConnector.source_type == JobSourceType.LINKEDIN_MCP


def test_normalize_legacy_dict_maps_aliases() -> None:
    connector = _job_connector()
    job = connector.normalize(_source_payload(), _source_config())
    assert job is not None
    assert isinstance(job, DiscoveredJob)
    assert job.external_id == "job-1"
    assert job.url == "https://m.linkedin.com/jobs/view/job-1"
    assert job.title == "Software Engineer Intern"
    assert job.company == "Acme"
    assert job.location == "Tunis, Tunisia"
    assert job.description == "Final year project internship"
    assert job.employment_type == "INTERNSHIP"
    assert job.remote_status == "hybrid"


def test_normalize_returns_none_without_title_or_url() -> None:
    connector = _job_connector()
    assert connector.normalize({"title": "No URL"}, _source_config()) is None
    assert connector.normalize({"url": "https://x"}, _source_config()) is None


def test_build_client_injects_playwright_browsers_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The spawned MCP server re-uses the installed browser cache, never a fresh download."""
    import app.infrastructure.job_sources.linkedin_mcp_connector as connector_module

    monkeypatch.setattr(
        connector_module, "playwright_browsers_path", lambda: "C:/cache/ms-playwright"
    )
    client = _job_connector()._build_client(
        _source_config(server_env={"FOO": "bar"})
    )
    assert client._params.env is not None
    assert client._params.env["PLAYWRIGHT_BROWSERS_PATH"] == "C:/cache/ms-playwright"
    assert client._params.env["FOO"] == "bar"


def test_normalize_handles_parsed_payload_shape() -> None:
    connector = _job_connector()
    job = connector.normalize(
        {
            "job_id": "101",
            "title": "Software Engineer Intern",
            "company": "Acme Tech",
            "location": "Tunis, Tunisia",
            "work_mode": "remote",
        },
        _source_config(),
    )
    assert job is not None
    assert job.external_id == "101"
    assert job.url == "https://www.linkedin.com/jobs/view/101/"
    assert job.remote_status == "remote"
    assert job.raw_payload["job_id"] == "101"


def test_validate_requires_command_when_no_default() -> None:
    connector = LinkedInMCPConnector(get_settings(), mcp_config=_empty_server())
    invalid = JobSourceConfig(
        id=1,
        name="linkedin",
        type=JobSourceType.LINKEDIN_MCP,
        base_url="",
        config={},
    )
    assert connector.validate(invalid) == ["server_command (or base_url) is required"]
    assert connector.validate(_source_config()) == []
    assert connector.validate(_source_config(server_command="python")) == []


def test_build_search_arguments_merges_source_filters() -> None:
    connector = _job_connector()
    args = connector._build_search_arguments(
        _source_config(keywords="Python", location="Tunis", job_type="INTERNSHIP")
    )
    assert args["keywords"] == "Python"
    assert args["location"] == "Tunis"
    assert args["job_type"] == "INTERNSHIP"
    assert "max_pages" in args


def test_extract_job_ids() -> None:
    assert _extract_job_ids({"job_ids": ["101", "102"]}) == ["101", "102"]
    assert _extract_job_ids({"job_ids": []}) == []
    assert _extract_job_ids({}) == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("uvx -y pkg", ["uvx", "-y", "pkg"]),
        (["uvx", "-y", "pkg"], ["uvx", "-y", "pkg"]),
    ],
)
def test_server_args_parsing(value: object, expected: list[str]) -> None:
    connector = _job_connector()
    client = connector._build_client(_source_config(server_command="echo", server_args=value))
    assert client._params.args == expected


def test_empty_server_args_uses_configured_defaults() -> None:
    connector = _job_connector()
    client = connector._build_client(_source_config(server_command="echo", server_args=""))
    assert client._params.args == connector._server.base_arguments()


def test_parse_call_result_text_content() -> None:
    from mcp.types import CallToolResult, TextContent

    result = CallToolResult(content=[TextContent(type="text", text='{"x": 1}')])
    assert _parse_call_result(result) == {"x": 1}


def test_parse_call_result_error_raises() -> None:
    from mcp.types import CallToolResult, TextContent

    result = CallToolResult(is_error=True, content=[TextContent(type="text", text="boom")])
    with pytest.raises(LinkedInMCPError):
        _parse_call_result(result)


def test_maybe_json() -> None:
    assert _maybe_json('{"k": 2}') == {"k": 2}
    assert _maybe_json("raw text") == "raw text"


def _source_payload() -> dict:
    return {
        "id": "job-1",
        "title": "Software Engineer Intern",
        "company_name": "Acme",
        "url": "https://m.linkedin.com/jobs/view/job-1",
        "location": "Tunis, Tunisia",
        "description": "Final year project internship",
        "employmentType": "INTERNSHIP",
        "remoteStatus": "hybrid",
    }


def _empty_server() -> object:
    from types import SimpleNamespace

    return SimpleNamespace(
        command="",
        cwd=".",
        timeout_seconds=30.0,
        tool_timeout_seconds=60.0,
        max_jobs=8,
        max_pages=3,
        expired_markers=(),
        max_matching_skills=5,
        max_missing_skills=5,
    )
