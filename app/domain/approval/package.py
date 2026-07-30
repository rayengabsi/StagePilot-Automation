from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.enums import ApprovalState


def build_snapshot(
    recommendation_data: dict[str, Any],
    profile_data: dict[str, Any],
    explanation: str,
    tailored_resume: dict[str, str] | None,
    cover_letter_body: str,
    email_draft: dict[str, str] | None,
    pdf_paths: list[str],
    docx_paths: list[str],
    template_name: str,
    theme_name: str,
    config_version: str = "1.0.0",
) -> str:
    """Build an immutable JSON snapshot of the application."""
    snapshot: dict[str, Any] = {
        "recommendation": recommendation_data,
        "profile": profile_data,
        "explanation": explanation,
        "tailored_resume": tailored_resume,
        "cover_letter_body": cover_letter_body,
        "email_draft": email_draft,
        "documents": {
            "pdf_paths": pdf_paths,
            "docx_paths": docx_paths,
        },
        "template_name": template_name,
        "theme_name": theme_name,
        "config_version": config_version,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return json.dumps(snapshot, sort_keys=True, default=str)


def build_documents_json(
    resume_pdf: str = "",
    resume_docx: str = "",
    cover_letter_pdf: str = "",
    cover_letter_docx: str = "",
    email_subject: str = "",
    email_body: str = "",
) -> str:
    """Build a JSON string of document paths."""
    docs: dict[str, str] = {
        "resume_pdf": resume_pdf,
        "resume_docx": resume_docx,
        "cover_letter_pdf": cover_letter_pdf,
        "cover_letter_docx": cover_letter_docx,
        "email_subject": email_subject,
        "email_body": email_body,
    }
    return json.dumps(docs, sort_keys=True)


def compute_hash(snapshot_json: str, documents_json: str) -> str:
    """Compute a deterministic SHA-256 hash for an application."""
    raw = snapshot_json + documents_json
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_application_package(
    recommendation_id: int,
    job_id: int,
    profile_id: int,
    final_score: float,
    snapshot_json: str,
    documents_json: str,
    profile_version: str = "current",
    template_name: str = "modern",
    theme_name: str = "default",
    priority: int = 0,
) -> ApplicationPackage:
    """Create a new ApplicationPackage with a computed hash."""
    app_hash = compute_hash(snapshot_json, documents_json)
    now = datetime.now(UTC).isoformat()
    return ApplicationPackage(
        recommendation_id=recommendation_id,
        job_id=job_id,
        profile_id=profile_id,
        final_score=final_score,
        snapshot_json=snapshot_json,
        documents_json=documents_json,
        application_hash=app_hash,
        profile_version=profile_version,
        template_name=template_name,
        theme_name=theme_name,
        status=ApprovalState.NEW,
        priority=priority,
        created_at=now,
        updated_at=now,
    )
