from __future__ import annotations

import json
from typing import Any

from app.domain.approval.entities import ApplicationPackage


def format_application_message(
    package: ApplicationPackage,
    queue_position: int | None = None,
    max_length: int = 4096,
) -> str:
    """Format an application package as a Telegram message."""
    lines: list[str] = []
    snapshot = _try_parse_json(package.snapshot_json)
    doc_data = _try_parse_json(package.documents_json)

    if snapshot:
        rec = snapshot.get("recommendation", {})
        job_data = rec.get("job", {})
        lines.append(f"*Company:* {job_data.get('company_name', 'N/A')}")
        lines.append(f"*Position:* {job_data.get('title', 'N/A')}")
        lines.append(f"*Location:* {job_data.get('location', 'N/A')}")
        lines.append(f"*Final Score:* {package.final_score:.1f}")
        matched = rec.get("matched_skills", [])
        missing = rec.get("missing_skills", [])
        if matched:
            lines.append(f"*Matched Skills:* {', '.join(matched[:8])}")
        if missing:
            lines.append(f"*Missing Skills:* {', '.join(missing[:5])}")
        explanation = snapshot.get("explanation", "")
        if explanation:
            truncated = explanation[:300]
            lines.append(f"*Explanation:* {truncated}")
    else:
        lines.append(f"*Package ID:* {package.id}")
        lines.append(f"*Score:* {package.final_score:.1f}")

    lines.append(f"*Status:* {package.status.value}")
    lines.append(f"*Template:* {package.template_name}")
    lines.append(f"*Revision:* {package.revision_number}")

    if doc_data:
        avail = []
        if doc_data.get("resume_pdf"):
            avail.append("Resume PDF")
        if doc_data.get("resume_docx"):
            avail.append("Resume DOCX")
        if doc_data.get("cover_letter_pdf"):
            avail.append("Cover Letter PDF")
        if doc_data.get("cover_letter_docx"):
            avail.append("Cover Letter DOCX")
        if avail:
            lines.append(f"*Documents:* {', '.join(avail)}")

    if queue_position is not None:
        lines.append(f"*Queue Position:* {queue_position + 1}")

    text = "\n".join(lines)
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."
    return text


def _try_parse_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, TypeError):
        return None
