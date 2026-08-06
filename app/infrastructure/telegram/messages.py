from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.domain.approval.entities import ApplicationPackage, ApprovalEvent

SEPARATOR = "━━━━━━━━━━━━━━━━━━━━"
UNKNOWN = "Not specified"


def format_application_message(
    package: ApplicationPackage,
    queue_position: int | None = None,
    max_length: int = 4096,
) -> str:
    """Format an approval package as a premium Telegram recommendation card."""
    return format_approval_message(package, queue_position=queue_position, max_length=max_length)


def format_recommendation_message(
    package: ApplicationPackage,
    queue_position: int | None = None,
    max_length: int = 4096,
) -> str:
    """Format a job recommendation for Telegram review."""
    snapshot = _try_parse_json(package.snapshot_json) or {}
    documents = _try_parse_json(package.documents_json) or {}
    rec = _recommendation(snapshot)
    job = _job(rec)
    insights = _insights(rec)
    quality = _quality(snapshot)

    company = _value(job, "company_name", "company", default=f"Package #{package.id}")
    title = _value(job, "title", "job_title", default="Role unavailable")
    location = _value(job, "location")
    work_mode = _value(job, "classification_work_mode", "remote_status", "work_mode")
    employment = _value(job, "classification_employment_type", "employment_type")
    seniority = _value(job, "classification_seniority", "seniority")
    posted_at = _format_date(_value(job, "posted_at", "posting_date", "created_at"))
    confidence = _value(insights, "confidence")
    why = _value(insights, "summary", default=_value(snapshot, "explanation", default=""))
    matched = _as_list(rec.get("matched_skills"))
    missing = _as_list(rec.get("missing_skills"))

    lines = [
        "🚀 *StagePilot Recommendation*",
        SEPARATOR,
        f"🏢 *{_md(company)}*",
        f"💼 {_md(title)}",
        f"📍 {_md(location)}  •  {_md(work_mode)}",
        "",
        f"🎯 *Match Score:* `{package.final_score:.1f}/100`",
        f"🧭 *Confidence:* `{_md(_humanize(confidence))}`",
        _status_pipeline(package.status.value),
    ]

    if queue_position is not None:
        lines.append(f"📌 *Queue Position:* `{queue_position + 1}`")

    lines.extend(["", "✨ *Why This Matches You*"])
    lines.extend(_bullets([why] if why else matched[:3], empty="No match summary available yet."))

    lines.extend(["", "🧩 *Missing Skills*"])
    lines.extend(_bullets(missing[:5], empty="No critical missing skills detected."))

    lines.extend(
        [
            "",
            "📋 *Job Summary*",
            f"• Employment: {_md(employment)}",
            f"• Seniority: {_md(seniority)}",
            f"• Posted: {_md(posted_at)}",
        ]
    )

    quality_lines = _quality_lines(quality)
    if quality_lines:
        lines.extend(["", "🧪 *Tailoring Quality*", *quality_lines])

    doc_lines = _document_lines(documents)
    if doc_lines:
        lines.extend(["", "📎 *Available Previews*", *doc_lines])

    lines.extend(
        [
            "",
            "🗂️ *Review Details*",
            f"• Status: `{_md(package.status.value)}`",
            f"• Template: {_md(package.template_name)}",
            f"• Revision: `{package.revision_number}`",
        ]
    )

    return _truncate("\n".join(lines), max_length)


def format_approval_message(
    package: ApplicationPackage,
    queue_position: int | None = None,
    max_length: int = 4096,
) -> str:
    """Format the main approval card."""
    return format_recommendation_message(package, queue_position, max_length)


def format_linked_match_message(
    *,
    title: str,
    company: str | None,
    location: str | None,
    url: str,
    final_score: float,
    why: str,
    matched_skills: list[str] | tuple[str, ...] = (),
    missing_skills: list[str] | tuple[str, ...] = (),
    salary: str | None = None,
    employment_type: str | None = None,
    experience_level: str | None = None,
    company_size: str | None = None,
    recruiter: str | None = None,
    posted_at: str | datetime | None = None,
    max_matching_skills: int = 5,
    max_missing_skills: int = 5,
    max_length: int = 4096,
) -> str:
    """Format a rich above-threshold LinkedIn match card for Telegram."""
    lines = [
        "🚀 *New Career Match*",
        SEPARATOR,
        "🏢 *Company*",
        " ".join(part for part in (company, company_size) if part) or UNKNOWN,
        "",
        "💼 *Position*",
        _md(title or UNKNOWN),
        "",
        "📍 *Location*",
        _md(location or UNKNOWN),
        "",
    ]

    facts = []
    if salary:
        facts.append(f"💰 *{_md(salary)}*")
    if posted_at:
        facts.append(f"📅 Posted {_md(_format_date(posted_at))}")
    if employment_type:
        facts.append(f"🧩 {_md(employment_type)}")
    if experience_level:
        facts.append(f"📈 {_md(experience_level)}")
    for fact in facts:
        lines.extend([fact, ""])

    lines.extend(
        [
            "🎯 *Match*",
            f"{final_score:.0f}%",
            "",
        ]
    )
    if matched_skills:
        lines.append("✅ *Matching Skills*")
        lines.extend(_bullets(list(matched_skills)[:max_matching_skills], empty=UNKNOWN))
        lines.append("")
    if missing_skills:
        lines.append("⚠️ *Missing Skills*")
        lines.extend(_bullets(list(missing_skills)[:max_missing_skills], empty=UNKNOWN))
        lines.append("")
    lines.extend(
        [
            "💡 *Why this matches*",
            "",
            _md(why or UNKNOWN),
            "",
        ]
    )
    if recruiter:
        lines.extend(["👤 *Recruiter*", _md(recruiter), ""])
    lines.extend(
        [
            "🔗 *Apply*",
            _md(url or UNKNOWN),
        ]
    )
    return _truncate("\n".join(lines), max_length)


def format_application_update_message(
    *,
    title: str,
    status: str,
    company: str | None = None,
    comment: str | None = None,
    max_length: int = 4096,
) -> str:
    """Format a lifecycle or metadata update notification."""
    lines = [
        "📣 *Application Update*",
        SEPARATOR,
        f"💼 {_md(title)}",
        f"🏢 {_md(company or UNKNOWN)}",
        f"🔄 Status: `{_md(_humanize(status))}`",
    ]
    if comment:
        lines.extend(["", f"💬 {_md(comment)}"])
    return _truncate("\n".join(lines), max_length)


def format_reminder_message(
    *,
    company: str,
    title: str,
    due_at: str | datetime | None = None,
    message: str | None = None,
    max_length: int = 4096,
) -> str:
    """Format a follow-up reminder notification."""
    lines = [
        "⏰ *Follow-Up Reminder*",
        SEPARATOR,
        f"🏢 {_md(company)}",
        f"💼 {_md(title)}",
        f"📅 Due: {_md(_format_date(due_at) if due_at else UNKNOWN)}",
    ]
    if message:
        lines.extend(["", f"📝 {_md(message)}"])
    return _truncate("\n".join(lines), max_length)


def format_interview_invitation_message(
    *,
    company: str,
    title: str,
    when: str | datetime | None = None,
    max_length: int = 4096,
) -> str:
    """Format an interview-stage notification."""
    return _truncate(
        "\n".join(
            [
                "🎙️ *Interview Invitation*",
                SEPARATOR,
                f"🏢 {_md(company)}",
                f"💼 {_md(title)}",
                f"📅 When: {_md(_format_date(when) if when else UNKNOWN)}",
                "",
                "Prepare your story, project highlights, and role-specific questions.",
            ]
        ),
        max_length,
    )


def format_offer_message(
    *,
    company: str,
    title: str,
    next_step: str | None = None,
    max_length: int = 4096,
) -> str:
    """Format an offer notification."""
    lines = [
        "🏆 *Offer Received*",
        SEPARATOR,
        f"🏢 {_md(company)}",
        f"💼 {_md(title)}",
    ]
    if next_step:
        lines.extend(["", f"➡️ Next: {_md(next_step)}"])
    return _truncate("\n".join(lines), max_length)


def format_rejection_message(
    *,
    company: str,
    title: str,
    note: str | None = None,
    max_length: int = 4096,
) -> str:
    """Format a rejection or closed-application notification."""
    lines = [
        "📭 *Application Closed*",
        SEPARATOR,
        f"🏢 {_md(company)}",
        f"💼 {_md(title)}",
        "Status: `Rejected`",
    ]
    if note:
        lines.extend(["", f"📝 {_md(note)}"])
    return _truncate("\n".join(lines), max_length)


def format_daily_summary_message(
    *,
    queued: int,
    approved: int = 0,
    applied: int = 0,
    interviews: int = 0,
    offers: int = 0,
    failed: int = 0,
    max_length: int = 4096,
) -> str:
    """Format a compact daily bot summary."""
    lines = [
        "📊 *Daily StagePilot Summary*",
        SEPARATOR,
        f"• New recommendations: `{queued}`",
        f"• Approved: `{approved}`",
        f"• Applied: `{applied}`",
        f"• Interviews: `{interviews}`",
        f"• Offers: `{offers}`",
    ]
    if failed:
        lines.append(f"• Needs attention: `{failed}`")
    lines.extend(["", "Use /queue to review pending applications."])
    return _truncate("\n".join(lines), max_length)


def format_queue_message(packages: list[ApplicationPackage], total_count: int) -> str:
    """Format the approval queue overview."""
    if not packages:
        return "✅ *Approval Queue*\n" + SEPARATOR + "\nNo applications waiting for review."

    lines = ["🧭 *Approval Queue*", SEPARATOR, f"Pending: `{total_count}`", ""]
    for index, package in enumerate(packages, start=1):
        snapshot = _try_parse_json(package.snapshot_json) or {}
        rec = _recommendation(snapshot)
        job = _job(rec)
        company = _value(job, "company_name", "company", default=f"Package #{package.id}")
        title = _value(job, "title", "job_title", default="Role unavailable")
        confidence = _humanize(_value(_insights(rec), "confidence"))
        lines.append(
            f"{index}. *{_md(company)}* - {_md(title)}\n"
            f"   Score `{package.final_score:.1f}` • {_md(confidence)} • `{package.status.value}`"
        )
    return _truncate("\n".join(lines), 4096)


def format_history_message(package_id: int, events: list[ApprovalEvent]) -> str:
    """Format application package history events."""
    if not events:
        return f"🕘 *Application History*\n{SEPARATOR}\nNo events recorded for `#{package_id}`."

    lines = ["🕘 *Application History*", SEPARATOR, f"Package `#{package_id}`", ""]
    for event in events[:20]:
        timestamp = _format_date(event.created_at)
        comment = f" - {_md(event.comment)}" if event.comment else ""
        lines.append(
            f"• `{timestamp}` {_md(_humanize(str(event.action)))} by {_md(event.actor)}{comment}"
        )
    if len(events) > 20:
        lines.append(f"• +{len(events) - 20} older events")
    return _truncate("\n".join(lines), 4096)


def format_status_message(package: ApplicationPackage) -> str:
    """Format the current package status."""
    snapshot = _try_parse_json(package.snapshot_json) or {}
    job = _job(_recommendation(snapshot))
    company = _value(job, "company_name", "company", default=f"Package #{package.id}")
    title = _value(job, "title", "job_title", default="Role unavailable")
    return format_application_update_message(
        title=title,
        company=company,
        status=package.status.value,
        comment=f"Score {package.final_score:.1f}/100 • Revision {package.revision_number}",
    )


def format_document_info_message(
    *,
    title: str,
    fields: dict[str, str],
    max_length: int = 4096,
) -> str:
    """Format document preview metadata."""
    lines = [f"📎 *{_md(title)}*", SEPARATOR]
    for label, value in fields.items():
        lines.append(f"• {_md(label)}: {_md(value or UNKNOWN)}")
    return _truncate("\n".join(lines), max_length)


def format_snapshot_preview(snapshot: dict[str, Any], max_length: int = 3000) -> str:
    """Format a compact package snapshot preview."""
    preview_keys = {k: v for k, v in snapshot.items() if k != "profile"}
    body = json.dumps(preview_keys, indent=2, default=str)[: max_length - 80]
    return f"📋 *Package Details*\n{SEPARATOR}\n```json\n{body}\n```"


def _status_pipeline(status: str) -> str:
    current = _stage_for_status(status)
    stages = ["Discovered", "Recommended", "Tailored", "Approved", "Applied"]
    rendered = []
    for stage in stages:
        rendered.append("●" if stages.index(stage) <= current else "○")
    return f"📍 *Progress:* {' '.join(rendered)}  `{' → '.join(stages)}`"


def _stage_for_status(status: str) -> int:
    if status == "approved":
        return 3
    if status == "archived":
        return 4
    if status in {"queued", "under_review", "revision_requested"}:
        return 2
    if status in {"new", "rejected", "skipped"}:
        return 1
    return 0


def _document_lines(documents: dict[str, Any]) -> list[str]:
    available = []
    if documents.get("resume_pdf"):
        available.append("Resume PDF")
    if documents.get("resume_docx"):
        available.append("Resume DOCX")
    if documents.get("cover_letter_pdf"):
        available.append("Cover Letter PDF")
    if documents.get("cover_letter_docx"):
        available.append("Cover Letter DOCX")
    if documents.get("email_subject") or documents.get("email_body"):
        available.append("Email Draft")
    return [f"• {_md(item)}" for item in available]


def _quality_lines(quality: dict[str, Any]) -> list[str]:
    if not quality:
        return []
    lines = []
    tailoring = _quality_report(quality, "cover_letter", "tailoring", "tailoring_quality")
    resume = _quality_report(quality, "resume", "resume_quality")
    if tailoring:
        lines.append(f"• AI Tailoring: {_quality_label(tailoring)}")
    if resume:
        lines.append(f"• Resume Quality: {_quality_label(resume)}")
    return lines


def _quality_report(quality: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = quality.get(key)
        if isinstance(value, dict):
            return value
    return None


def _quality_label(report: dict[str, Any]) -> str:
    score = report.get("overall_score", report.get("score"))
    level = _humanize(str(report.get("overall_quality", report.get("quality", ""))))
    if isinstance(score, int | float):
        return f"`{score:.1f}/100` {_md(level)}" if level else f"`{score:.1f}/100`"
    return _md(level or UNKNOWN)


def _recommendation(snapshot: dict[str, Any]) -> dict[str, Any]:
    rec = snapshot.get("recommendation")
    return rec if isinstance(rec, dict) else {}


def _job(recommendation: dict[str, Any]) -> dict[str, Any]:
    job = recommendation.get("job")
    return job if isinstance(job, dict) else {}


def _insights(recommendation: dict[str, Any]) -> dict[str, Any]:
    insights = recommendation.get("insights")
    return insights if isinstance(insights, dict) else {}


def _quality(snapshot: dict[str, Any]) -> dict[str, Any]:
    quality = snapshot.get("quality")
    return quality if isinstance(quality, dict) else {}


def _value(data: dict[str, Any], *keys: str, default: str = UNKNOWN) -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _as_list(value: object) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value if item]
    return []


def _bullets(values: list[str], *, empty: str) -> list[str]:
    if not values:
        return [f"• {_md(empty)}"]
    return [f"• {_md(value)}" for value in values]


def _humanize(value: str) -> str:
    if not value or value == UNKNOWN:
        return UNKNOWN
    return value.replace("_", " ").strip().title()


def _format_date(value: str | datetime | None) -> str:
    if value in (None, ""):
        return UNKNOWN
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%d")
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return text[:10] if len(text) > 10 else text


def _md(value: str) -> str:
    return str(value).replace("_", "\\_").replace("*", "")


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _try_parse_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, TypeError):
        return None
