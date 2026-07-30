from __future__ import annotations

from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.enums import ApprovalState
from app.infrastructure.telegram.messages import format_application_message


def _make_package(
    score: float = 85.0,
    status: ApprovalState = ApprovalState.QUEUED,
    has_snapshot: bool = True,
) -> ApplicationPackage:
    snapshot = (
        '{"recommendation": {"job": {"company_name": "Acme Corp",'
        ' "title": "Engineer", "location": "NYC"},'
        '"matched_skills": ["Python", "SQL"], "missing_skills": ["Go"]},'
        '"explanation": "Great skills match for the role."}'
        if has_snapshot
        else "{}"
    )
    docs = (
        '{"resume_pdf": "resume.pdf", "resume_docx": "resume.docx",'
        '"cover_letter_pdf": "cover.pdf", "cover_letter_docx": "cover.docx"}'
    )
    return ApplicationPackage(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        final_score=score,
        snapshot_json=snapshot,
        documents_json=docs,
        application_hash="abc123",
        status=status,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )


def test_format_message_contains_company() -> None:
    pkg = _make_package()
    text = format_application_message(pkg)
    assert "Acme Corp" in text
    assert "Engineer" in text
    assert "NYC" in text


def test_format_message_contains_score() -> None:
    pkg = _make_package(score=92.5)
    text = format_application_message(pkg)
    assert "92.5" in text


def test_format_message_contains_skills() -> None:
    pkg = _make_package()
    text = format_application_message(pkg)
    assert "Python" in text
    assert "SQL" in text
    assert "Go" in text


def test_format_message_contains_status() -> None:
    pkg = _make_package(status=ApprovalState.UNDER_REVIEW)
    text = format_application_message(pkg)
    assert "under_review" in text


def test_format_message_with_queue_position() -> None:
    pkg = _make_package()
    text = format_application_message(pkg, queue_position=2)
    assert "Queue Position" in text
    assert "3" in text


def test_format_message_without_snapshot() -> None:
    pkg = _make_package(has_snapshot=False)
    text = format_application_message(pkg)
    assert "Package ID" in text
    assert "Score" in text


def test_format_message_shows_documents() -> None:
    pkg = _make_package()
    text = format_application_message(pkg)
    assert "Resume PDF" in text
    assert "Resume DOCX" in text
    assert "Cover Letter PDF" in text


def test_format_message_max_length() -> None:
    long_name = "A" * 5000
    skills_list = ["Skill"] * 200
    long_explanation = "X" * 5000
    snapshot_json = (
        '{"recommendation": {"job": {"company_name": "'
        + long_name
        + '"}, "matched_skills": '
        + str(skills_list)
        + ', "explanation": "'
        + long_explanation
        + '"}'
    )
    docs_json = "{}"
    pkg = ApplicationPackage(
        id=1,
        recommendation_id=1,
        job_id=1,
        profile_id=1,
        final_score=50.0,
        snapshot_json=snapshot_json,
        documents_json=docs_json,
        application_hash="hash",
        status=ApprovalState.QUEUED,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )
    text = format_application_message(pkg, max_length=500)
    assert len(text) <= 500
