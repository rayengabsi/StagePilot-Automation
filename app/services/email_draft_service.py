from __future__ import annotations

from app.domain.ai.entities import CoverLetter, EmailDraft
from app.domain.ai.enums import AIFeature
from app.services.ai_orchestrator import AIOrchestrator


class EmailDraftService:
    """Draft a professional application email using AI.

    Only drafts emails. Never sends them.
    """

    def __init__(self, orchestrator: AIOrchestrator) -> None:
        self._orchestrator = orchestrator

    def draft(
        self,
        cover_letter: CoverLetter,
        company: str = "",
        job_title: str = "",
        recipient: str = "",
        candidate_name: str = "",
    ) -> EmailDraft:
        variables = {
            "recipient": recipient or "Hiring Manager",
            "company": company,
            "job_title": job_title,
            "cover_letter_body": cover_letter.body,
            "candidate_name": candidate_name,
        }

        data = self._orchestrator.generate_json(
            prompt_name="email_application",
            variables=variables,
            feature=AIFeature.EMAIL_DRAFT,
            required_fields=["subject", "body", "signature"],
        )

        return EmailDraft(
            subject=str(data.get("subject", "")),
            body=str(data.get("body", "")),
            recipient=recipient or None,
            signature=str(data.get("signature", "")),
        )
