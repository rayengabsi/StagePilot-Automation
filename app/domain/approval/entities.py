from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.approval.enums import ApprovalAction, ApprovalState


@dataclass(frozen=True, slots=True)
class ApplicationPackage:
    recommendation_id: int
    job_id: int
    profile_id: int
    final_score: float

    snapshot_json: str
    documents_json: str
    application_hash: str

    profile_version: str
    template_name: str
    theme_name: str

    status: ApprovalState = ApprovalState.NEW
    priority: int = 0
    revision_number: int = 0
    telegram_message_id: int | None = None

    id: int = 0
    created_at: str = ""
    updated_at: str = ""
    approved_at: str | None = None
    reviewed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "recommendation_id": self.recommendation_id,
            "job_id": self.job_id,
            "profile_id": self.profile_id,
            "final_score": self.final_score,
            "status": self.status.value,
            "priority": self.priority,
            "revision_number": self.revision_number,
            "profile_version": self.profile_version,
            "template_name": self.template_name,
            "theme_name": self.theme_name,
            "application_hash": self.application_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approved_at": self.approved_at,
            "reviewed_at": self.reviewed_at,
        }


@dataclass(frozen=True, slots=True)
class ApprovalEvent:
    package_id: int
    action: ApprovalAction
    actor: str
    comment: str = ""
    previous_state: ApprovalState | None = None
    new_state: ApprovalState | None = None

    id: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "package_id": self.package_id,
            "action": self.action.value,
            "actor": self.actor,
            "comment": self.comment,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "new_state": self.new_state.value if self.new_state else None,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ApprovalComment:
    package_id: int
    author: str
    text: str
    id: int = 0
    created_at: str = ""
