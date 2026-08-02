from __future__ import annotations

import json

from app.domain.approval.entities import ApplicationPackage, ApprovalEvent
from app.domain.approval.enums import ApprovalAction, ApprovalState
from app.infrastructure.telegram.messages import (
    format_application_message,
    format_application_update_message,
    format_daily_summary_message,
    format_document_info_message,
    format_history_message,
    format_interview_invitation_message,
    format_offer_message,
    format_queue_message,
    format_rejection_message,
    format_reminder_message,
    format_snapshot_preview,
    format_status_message,
)


def _make_package(
    score: float = 85.0,
    status: ApprovalState = ApprovalState.QUEUED,
    has_snapshot: bool = True,
) -> ApplicationPackage:
    snapshot = {
        "recommendation": {
            "job": {
                "company_name": "Acme Corp",
                "title": "Backend Engineer",
                "location": "Paris",
                "classification_work_mode": "remote",
                "classification_employment_type": "Internship",
                "classification_seniority": "Junior",
                "posted_at": "2026-08-01T09:00:00+00:00",
                "url": "https://example.com/job",
            },
            "matched_skills": ["Python", "SQL"],
            "missing_skills": ["Go"],
            "insights": {
                "confidence": "very_high",
                "summary": "Strong Python and SQL match for the role.",
            },
        },
        "explanation": "Great skills match for the role.",
        "quality": {
            "resume": {"overall_score": 91.2, "overall_quality": "excellent"},
            "cover_letter": {"overall_score": 84.5, "overall_quality": "good"},
        },
    }
    docs = {
        "resume_pdf": "resume.pdf",
        "resume_docx": "resume.docx",
        "cover_letter_pdf": "cover.pdf",
        "cover_letter_docx": "cover.docx",
        "email_subject": "Application",
    }
    return ApplicationPackage(
        id=1,
        recommendation_id=10,
        job_id=20,
        profile_id=30,
        final_score=score,
        snapshot_json=json.dumps(snapshot if has_snapshot else {}),
        documents_json=json.dumps(docs),
        application_hash="abc123",
        status=status,
        profile_version="v1",
        template_name="modern",
        theme_name="default",
    )


def test_application_message_premium_snapshot() -> None:
    text = format_application_message(_make_package(score=92.5), queue_position=2)

    assert "🚀 *StagePilot Recommendation*" in text
    assert "🏢 *Acme Corp*" in text
    assert "💼 Backend Engineer" in text
    assert "📍 Paris" in text
    assert "🎯 *Match Score:* `92.5/100`" in text
    assert "🧭 *Confidence:* `Very High`" in text
    assert "✨ *Why This Matches You*" in text
    assert "Strong Python and SQL match" in text
    assert "🧩 *Missing Skills*" in text
    assert "Go" in text
    assert "📋 *Job Summary*" in text
    assert "AI Tailoring: `84.5/100` Good" in text
    assert "Resume Quality: `91.2/100` Excellent" in text
    assert "📌 *Queue Position:* `3`" in text


def test_application_message_gracefully_degrades_without_snapshot() -> None:
    text = format_application_message(_make_package(has_snapshot=False))

    assert "Package #1" in text
    assert "Role unavailable" in text
    assert "No match summary available yet" in text
    assert "Not specified" in text


def test_application_message_max_length() -> None:
    pkg = _make_package()
    text = format_application_message(pkg, max_length=500)
    assert len(text) <= 500


def test_queue_message_template() -> None:
    text = format_queue_message([_make_package()], total_count=1)
    assert "🧭 *Approval Queue*" in text
    assert "Pending: `1`" in text
    assert "Acme Corp" in text


def test_status_and_update_templates() -> None:
    status = format_status_message(_make_package(status=ApprovalState.UNDER_REVIEW))
    update = format_application_update_message(
        title="Backend Engineer",
        company="Acme Corp",
        status="interview",
        comment="Phone screen booked",
    )

    assert "📣 *Application Update*" in status
    assert "Under Review" in status
    assert "Phone screen booked" in update


def test_history_template() -> None:
    event = ApprovalEvent(
        package_id=1,
        action=ApprovalAction.APPROVED,
        actor="tester",
        comment="Looks good",
        created_at="2026-08-02T10:00:00+00:00",
    )
    text = format_history_message(1, [event])
    assert "🕘 *Application History*" in text
    assert "Approved by tester" in text
    assert "Looks good" in text


def test_reminder_template() -> None:
    text = format_reminder_message(
        company="Acme Corp",
        title="Backend Engineer",
        due_at="2026-08-04T09:00:00+00:00",
        message="Send a polite follow-up.",
    )
    assert "⏰ *Follow-Up Reminder*" in text
    assert "2026-08-04" in text


def test_interview_offer_rejection_templates() -> None:
    interview = format_interview_invitation_message(
        company="Acme Corp", title="Backend Engineer", when="2026-08-05"
    )
    offer = format_offer_message(
        company="Acme Corp", title="Backend Engineer", next_step="Review contract"
    )
    rejection = format_rejection_message(
        company="Acme Corp", title="Backend Engineer", note="Keep warm for future roles"
    )

    assert "🎙️ *Interview Invitation*" in interview
    assert "🏆 *Offer Received*" in offer
    assert "📭 *Application Closed*" in rejection


def test_daily_summary_template() -> None:
    text = format_daily_summary_message(
        queued=3, approved=1, applied=1, interviews=1, offers=0, failed=2
    )
    assert "📊 *Daily StagePilot Summary*" in text
    assert "New recommendations: `3`" in text
    assert "Needs attention: `2`" in text


def test_document_and_snapshot_templates() -> None:
    docs = format_document_info_message(
        title="Resume Preview", fields={"PDF": "resume.pdf", "DOCX": ""}
    )
    snapshot = format_snapshot_preview({"recommendation": {"id": 1}, "profile": {"pii": True}})

    assert "📎 *Resume Preview*" in docs
    assert "DOCX: Not specified" in docs
    assert "📋 *Package Details*" in snapshot
    assert "profile" not in snapshot
