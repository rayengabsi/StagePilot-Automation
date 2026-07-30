from __future__ import annotations

import json

from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.enums import ApprovalState
from app.domain.approval.package import (
    build_documents_json,
    build_snapshot,
    compute_hash,
    create_application_package,
)


def test_create_package() -> None:
    snap = build_snapshot(
        recommendation_data={"job": {"id": 1}},
        profile_data={"name": "Test User"},
        explanation="Great fit",
        tailored_resume={"summary": "Experienced developer"},
        cover_letter_body="Dear Sir",
        email_draft={"subject": "Application", "body": "Hello"},
        pdf_paths=["resume.pdf"],
        docx_paths=["resume.docx"],
        template_name="modern",
        theme_name="default",
    )
    docs = build_documents_json(
        resume_pdf="resume.pdf",
        resume_docx="resume.docx",
        cover_letter_pdf="cover.pdf",
        email_subject="Application",
        email_body="Hello",
    )
    package = create_application_package(
        recommendation_id=1,
        job_id=2,
        profile_id=3,
        final_score=85.5,
        snapshot_json=snap,
        documents_json=docs,
        template_name="modern",
        theme_name="default",
    )
    assert package.recommendation_id == 1
    assert package.job_id == 2
    assert package.profile_id == 3
    assert package.final_score == 85.5
    assert package.status == ApprovalState.NEW
    assert package.template_name == "modern"
    assert package.theme_name == "default"
    assert package.application_hash != ""
    assert isinstance(package.created_at, str)
    assert package.created_at != ""


def test_package_hash_unique_for_different_data() -> None:
    snap1 = build_snapshot(
        recommendation_data={"job": {"id": 1}},
        profile_data={"name": "User A"},
        explanation="Good",
        tailored_resume=None,
        cover_letter_body="Letter A",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="modern",
        theme_name="default",
    )
    snap2 = build_snapshot(
        recommendation_data={"job": {"id": 2}},
        profile_data={"name": "User B"},
        explanation="Also good",
        tailored_resume=None,
        cover_letter_body="Letter B",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="executive",
        theme_name="default",
    )
    docs = build_documents_json()
    h1 = compute_hash(snap1, docs)
    h2 = compute_hash(snap2, docs)
    assert h1 != h2


def test_package_hash_deterministic() -> None:
    snap = build_snapshot(
        recommendation_data={"job": {"id": 1}},
        profile_data={"name": "Test"},
        explanation="",
        tailored_resume=None,
        cover_letter_body="",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="modern",
        theme_name="default",
    )
    docs = build_documents_json()
    h1 = compute_hash(snap, docs)
    h2 = compute_hash(snap, docs)
    assert h1 == h2


def test_build_documents_json() -> None:
    docs = build_documents_json(
        resume_pdf="resume.pdf",
        resume_docx="resume.docx",
        cover_letter_pdf="cover.pdf",
        cover_letter_docx="cover.docx",
        email_subject="Application",
        email_body="Hello world",
    )
    parsed = json.loads(docs)
    assert parsed["resume_pdf"] == "resume.pdf"
    assert parsed["cover_letter_docx"] == "cover.docx"
    assert parsed["email_subject"] == "Application"


def test_build_snapshot_contains_all_required_keys() -> None:
    snap = build_snapshot(
        recommendation_data={},
        profile_data={},
        explanation="test",
        tailored_resume=None,
        cover_letter_body="",
        email_draft=None,
        pdf_paths=[],
        docx_paths=[],
        template_name="test",
        theme_name="test",
    )
    parsed = json.loads(snap)
    assert "recommendation" in parsed
    assert "profile" in parsed
    assert "explanation" in parsed
    assert "documents" in parsed
    assert "template_name" in parsed
    assert "theme_name" in parsed
    assert "config_version" in parsed
    assert "timestamp" in parsed


def test_application_package_to_dict() -> None:
    package = ApplicationPackage(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        final_score=90.0,
        snapshot_json="{}",
        documents_json="{}",
        application_hash="abc123",
        profile_version="current",
        template_name="modern",
        theme_name="default",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )
    d = package.to_dict()
    assert d["id"] == 1
    assert d["final_score"] == 90.0
    assert d["status"] == "new"
    assert d["application_hash"] == "abc123"
    assert d["template_name"] == "modern"
