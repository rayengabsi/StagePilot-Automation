from __future__ import annotations

import json
from typing import Any

from app.domain.approval.package import build_snapshot


class SnapshotService:
    """Creates and validates immutable application snapshots."""

    def create_snapshot(
        self,
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
        return build_snapshot(
            recommendation_data=recommendation_data,
            profile_data=profile_data,
            explanation=explanation,
            tailored_resume=tailored_resume,
            cover_letter_body=cover_letter_body,
            email_draft=email_draft,
            pdf_paths=pdf_paths,
            docx_paths=docx_paths,
            template_name=template_name,
            theme_name=theme_name,
            config_version=config_version,
        )

    def validate_snapshot(self, snapshot_json: str) -> bool:
        try:
            data = json.loads(snapshot_json)
            required = [
                "recommendation",
                "profile",
                "explanation",
                "documents",
                "template_name",
                "theme_name",
                "config_version",
                "timestamp",
            ]
            return all(k in data for k in required)
        except (json.JSONDecodeError, TypeError):
            return False

    def extract_field(self, snapshot_json: str, field_path: str) -> Any:  # noqa: ANN401
        data = json.loads(snapshot_json)
        parts = field_path.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current[part]
            else:
                msg = f"Field path '{field_path}' not found"
                raise KeyError(msg)
        return current
