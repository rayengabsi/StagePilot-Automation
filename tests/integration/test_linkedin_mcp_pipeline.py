"""Milestone 2: LinkedIn MCP jobs flow through the existing matching pipeline.

Demonstrates, end to end against the local fake MCP server:
  - job retrieved from LinkedIn MCP
  - job normalized (ingested as a persisted Job)
  - match score calculated by the existing recommendation engine
  - explanation generated from the explainable scoring artifacts
  - jobs filtered by the configured recommendation cutoff threshold
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.db.models.jobs import JobSource
from app.db.models.profile import (
    PreferenceRecord,
    ProfileVersionRecord,
    SkillRecord,
)
from app.db.models.profile import Profile as ProfileRecord
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceConfigError
from app.services.linkedin_mcp_pipeline_service import LinkedInMCPPipelineService
from sqlalchemy.orm import Session

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FAKE_SERVER = _REPO_ROOT / "scripts" / "fake_linkedin_mcp_server.py"


def _add_profile(session: Session) -> ProfileRecord:
    """Create an active profile with Python skills and a remote preference."""
    profile = ProfileRecord(active=True)
    session.add(profile)
    session.flush()
    session.add(
        ProfileVersionRecord(
            profile_id=profile.id,
            version_number=1,
            snapshot_json={"personal_info": {"full_name": "Test User", "location": "Paris"}},
            completeness_score=80.0,
            change_description="initial",
        )
    )
    session.add(SkillRecord(profile_id=profile.id, name="Python"))
    session.add(SkillRecord(profile_id=profile.id, name="Backend"))
    session.add(PreferenceRecord(profile_id=profile.id, remote_preference="hybrid"))
    session.commit()
    return profile


def _add_linkedin_source(session: Session, keywords: str | None = None) -> JobSource:
    """Create an active LinkedIn MCP source pointing at the fake server."""
    config: dict = {
        "tool_name": "search_roles",
        "server_args": [str(_FAKE_SERVER)],
        "server_cwd": str(_REPO_ROOT),
    }
    if keywords:
        config["keywords"] = keywords
    source = JobSource(
        name="LinkedIn Fake",
        type=JobSourceType.LINKEDIN_MCP.value,
        base_url=sys.executable,
        config_json=config,
        is_active=True,
    )
    session.add(source)
    session.commit()
    return source


def test_linkedin_job_flows_through_matching_pipeline(db_session: Session) -> None:
    """Fetched LinkedIn jobs are normalized, scored, explained, and filtered."""
    _add_profile(db_session)
    _add_linkedin_source(db_session, keywords="Software")

    result = LinkedInMCPPipelineService(session=db_session).run()

    assert result.fetched >= 1
    assert result.inserted >= 1
    assert result.matched_total >= 1
    assert result.recommendations

    rec = result.recommendations[0]
    assert rec.final_score > 0
    assert rec.explanation
    assert "Software Engineer Intern" in rec.title
    assert "linkedin.com" in rec.url
    assert rec.location
    assert rec.to_dict()["location"] == rec.location
    assert result.cutoff == 30.0
    assert result.above_threshold + result.below_threshold == result.matched_total
    # Every result must be independently threshold-flagged.
    for item in result.recommendations:
        expected = item.final_score >= result.cutoff
        assert item.above_threshold == expected


def test_linkedin_mcp_threshold_keeps_only_above_cutoff(db_session: Session) -> None:
    """Raising the cutoff filters all recommendations below the threshold."""
    _add_profile(db_session)
    _add_linkedin_source(db_session)

    service = LinkedInMCPPipelineService(session=db_session, cutoff=10_000.0)

    result = service.run()

    if result.matched_total:
        assert result.above_threshold == 0
        assert result.below_threshold == result.matched_total
        assert all(not item.above_threshold for item in result.recommendations)


def test_linkedin_pipeline_requires_a_configured_source(db_session: Session) -> None:
    """Running without an active LinkedIn source raises a helpful error."""
    _add_profile(db_session)

    service = LinkedInMCPPipelineService(session=db_session)
    try:
        service.run()
    except SourceConfigError as exc:
        assert "add-linkedin-mcp" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected SourceConfigError")
