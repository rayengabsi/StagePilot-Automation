from __future__ import annotations

import json

import pytest
from app.services.snapshot_service import SnapshotService


@pytest.fixture
def svc() -> SnapshotService:
    return SnapshotService()


def test_create_snapshot(svc: SnapshotService) -> None:
    snap = svc.create_snapshot(
        recommendation_data={"job": {"title": "Engineer", "company": "Acme"}},
        profile_data={"name": "Alice", "skills": ["Python"]},
        explanation="Excellent match due to Python skills.",
        tailored_resume={"summary": "5 years Python experience"},
        cover_letter_body="Dear Hiring Manager",
        email_draft={"subject": "Application", "body": "Please find attached"},
        pdf_paths=["output/resume.pdf"],
        docx_paths=["output/resume.docx"],
        template_name="modern",
        theme_name="default",
    )
    parsed = json.loads(snap)
    assert parsed["recommendation"]["job"]["title"] == "Engineer"
    assert parsed["profile"]["name"] == "Alice"
    assert "Excellent match" in parsed["explanation"]


def test_validate_snapshot_valid(svc: SnapshotService) -> None:
    snap = svc.create_snapshot(
        recommendation_data={},
        profile_data={},
        explanation="",
        tailored_resume=None,
        cover_letter_body="",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="tpl",
        theme_name="thm",
    )
    assert svc.validate_snapshot(snap) is True


def test_validate_snapshot_invalid(svc: SnapshotService) -> None:
    assert svc.validate_snapshot("{}") is False
    assert svc.validate_snapshot("not json") is False
    assert svc.validate_snapshot('{"recommendation": {}}') is False


def test_extract_field(svc: SnapshotService) -> None:
    snap = svc.create_snapshot(
        recommendation_data={"job": {"company": "Acme Corp"}},
        profile_data={},
        explanation="",
        tailored_resume=None,
        cover_letter_body="",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="tpl",
        theme_name="thm",
    )
    result = svc.extract_field(snap, "recommendation.job.company")
    assert result == "Acme Corp"


def test_extract_field_missing(svc: SnapshotService) -> None:
    snap = svc.create_snapshot(
        recommendation_data={},
        profile_data={},
        explanation="",
        tailored_resume=None,
        cover_letter_body="",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="tpl",
        theme_name="thm",
    )
    with pytest.raises(KeyError):
        svc.extract_field(snap, "nonexistent.field")
