from __future__ import annotations

import sys
from pathlib import Path

from app.config.settings import get_settings
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.linkedin_mcp_connector import LinkedInMCPConnector

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FAKE_SERVER = _REPO_ROOT / "scripts" / "fake_linkedin_mcp_server.py"


def _server_source(**config: object) -> JobSourceConfig:
    merged: dict[str, object] = {
        "tool_name": "search_roles",
        "server_args": [str(_FAKE_SERVER)],
        "server_cwd": str(_REPO_ROOT),
    }
    merged.update(config)
    return JobSourceConfig(
        id=1,
        name="linkedin-fake",
        type=JobSourceType.LINKEDIN_MCP,
        base_url=sys.executable,
        config=merged,
    )


def _server_config(**config: object) -> JobSourceConfig:
    return _server_source(**config)


def test_linkedin_mcp_health_is_healthy() -> None:
    connector = LinkedInMCPConnector(get_settings())
    health = connector.health(_server_config())
    assert health.status == "healthy"
    assert health.provider == "linkedin_mcp"
    assert "search_roles" in health.message


def test_linkedin_mcp_fetches_jobs_end_to_end() -> None:
    connector = LinkedInMCPConnector(get_settings())
    source = _server_config()
    jobs = connector.fetch(source)
    assert jobs
    retrieved = sorted(jobs, key=lambda j: (j.external_id or ""))
    assert any(job.external_id == "MOCK-101" for job in retrieved)
    sample = next(j for j in retrieved if j.external_id == "MOCK-101")
    assert "Intern" in sample.title or "PFE" in sample.title
    assert sample.location
    assert sample.url.startswith("https://www.linkedin.com/jobs/")
    assert sample.company
    assert sample.raw_payload


def test_linkedin_mcp_keyword_filtering() -> None:
    connector = LinkedInMCPConnector(get_settings())
    jobs = connector.fetch(_server_config(keywords="Data Science"))
    assert jobs
    assert jobs[0].external_id == "MOCK-102"


def test_linkedin_mcp_is_registered() -> None:
    from app.infrastructure.job_sources.registry import get_connector_class

    connector_class = get_connector_class("linkedin_mcp")
    assert connector_class is LinkedInMCPConnector
