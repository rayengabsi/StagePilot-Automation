from __future__ import annotations

import sys
from pathlib import Path

import pytest
from app.config.settings import get_settings
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import LinkedInSessionExpiredError
from app.infrastructure.job_sources.linkedin_mcp_connector import LinkedInMCPConnector

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STUB_SERVER = _REPO_ROOT / "scripts" / "stub_linkedin_mcp_server.py"


def _server_source(**config: object) -> JobSourceConfig:
    merged: dict[str, object] = {
        "search_tool": "search_jobs",
        "detail_tool": "get_job_details",
        "server_command": sys.executable,
        "server_args": [str(_STUB_SERVER)],
    }
    if config.pop("_expired", False):
        merged["server_args"] = [str(_STUB_SERVER), "--expired"]
    merged.update(config)
    return JobSourceConfig(
        id=1,
        name="linkedin-stub",
        type=JobSourceType.LINKEDIN_MCP,
        base_url=sys.executable,
        config=merged,
    )


def test_linkedin_mcp_health_advertises_search_and_detail() -> None:
    connector = LinkedInMCPConnector(get_settings())
    health = connector.health(_server_source())
    assert health.status == "healthy"
    assert health.provider == "linkedin_mcp"
    assert "search_jobs" in health.message
    assert "get_job_details" in health.message


def test_linkedin_mcp_fetches_jobs_end_to_end() -> None:
    connector = LinkedInMCPConnector(get_settings())
    source = _server_source()
    jobs = connector.fetch(source)
    assert jobs
    retrieved = sorted(jobs, key=lambda j: (j.external_id or ""))
    assert any(job.external_id == "101" for job in retrieved)
    sample = next(j for j in retrieved if j.external_id == "101")
    assert "Software Engineer Intern" in sample.title
    assert sample.location
    assert sample.url == "https://www.linkedin.com/jobs/view/101/"
    assert sample.company == "Acme Tech"
    assert sample.raw_payload


def test_linkedin_mcp_keyword_filtering() -> None:
    connector = LinkedInMCPConnector(get_settings())
    jobs = connector.fetch(_server_source(keywords="Data Science"))
    assert jobs
    assert jobs[0].external_id == "102"


def test_linkedin_mcp_raises_on_expired_session() -> None:
    connector = LinkedInMCPConnector(get_settings())
    with pytest.raises(LinkedInSessionExpiredError):
        connector.fetch(_server_source(_expired=True))


def test_linkedin_mcp_is_registered() -> None:
    from app.infrastructure.job_sources.registry import get_connector_class

    connector_class = get_connector_class("linkedin_mcp")
    assert connector_class is LinkedInMCPConnector
