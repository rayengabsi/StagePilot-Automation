from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.linkedin_mcp_connector import (
    LinkedInMCPConnector,
    _extract_job_items,
)
from app.infrastructure.linkedin_mcp.client import (
    LinkedInMCPError,
    _maybe_json,
    _parse_call_result,
)


def _job_connector() -> LinkedInMCPConnector:
    from app.config.settings import get_settings

    return LinkedInMCPConnector(get_settings())


def _source() -> dict:
    return {
        "id": "job-1",
        "title": "Software Engineer Intern",
        "company_name": "Acme",
        "url": "https://m.linkedin.com/jobs/view/job-1",
        "location": "Tunis, Tunisia",
        "description": "<p>Final year project internship</p>",
        "employmentType": "INTERNSHIP",
        "remoteStatus": "hybrid",
    }


def _source_config(**config: object) -> JobSourceConfig:
    merged: dict[str, object] = {"tool_name": "search_roles"}
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


def test_normalize_maps_aliases() -> None:
    connector = _job_connector()
    job = connector.normalize(_source(), _source_config())
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


def test_normalize_uses_city_alias() -> None:
    connector = _job_connector()
    job = connector.normalize(
        {"job_title": "Data Apprentice", "external_url": "https://y/j", "city": "Paris"},
        _source_config(),
    )
    assert job is not None
    assert job.title == "Data Apprentice"
    assert job.url == "https://y/j"
    assert job.location == "Paris"


def test_normalize_external_id_falls_back_to_url() -> None:
    connector = _job_connector()
    job = connector.normalize({"title": "Role", "url": "https://z/1"}, _source_config())
    assert job is not None
    assert job.external_id == "https://z/1"
    assert job.raw_payload == {"title": "Role", "url": "https://z/1"}


def test_validate_requires_command() -> None:
    connector = _job_connector()
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


def test_build_arguments_includes_only_set_filters() -> None:
    connector = _job_connector()
    args = connector._build_arguments(
        _source_config(keywords="Python", location="Tunis", job_type="INTERNSHIP", limit=7)
    )
    assert args == {
        "keywords": "Python",
        "location": "Tunis",
        "job_type": "INTERNSHIP",
        "limit": 7,
    }
    assert connector._build_arguments(_source_config()) == {}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("uvx -y pkg", ["uvx", "-y", "pkg"]),
        (["uvx", "-y", "pkg"], ["uvx", "-y", "pkg"]),
        ("", []),
    ],
)
def test_server_args_parsing(value: object, expected: list[str]) -> None:
    connector = _job_connector()
    client = connector._build_client(_source_config(server_command="echo", server_args=value))
    assert client._params.args == expected


def test_fetch_returns_normalized_jobs() -> None:
    connector = _job_connector()
    fake_client = MagicMock()
    fake_client.call_tool.return_value = [_source(), _source()]
    with patch(
        "app.infrastructure.job_sources.linkedin_mcp_connector.LinkedInMCPClient",
        return_value=fake_client,
    ):
        jobs = connector.fetch(_source_config())
    assert len(jobs) == 2
    assert all(isinstance(job, DiscoveredJob) for job in jobs)
    fake_client.call_tool.assert_called_once_with("search_roles", {})


def test_extract_job_items_handles_shapes() -> None:
    raw = [{"title": "a"}, {"title": "b"}]
    assert _extract_job_items(raw) == raw
    assert _extract_job_items({"jobs": [{"title": "a"}]}) == [{"title": "a"}]
    assert _extract_job_items({"title": "solo", "url": "u"}) == [{"title": "solo", "url": "u"}]
    assert _extract_job_items("not-a-dict") == []


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
