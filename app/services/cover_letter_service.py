from __future__ import annotations

from app.domain.ai.entities import CoverLetter
from app.domain.ai.enums import AIFeature
from app.domain.master_profile.entities import MasterProfile
from app.domain.recommendation.entities import Recommendation
from app.services.ai_orchestrator import AIOrchestrator


class CoverLetterService:
    """Generate a personalized cover letter using AI."""

    def __init__(self, orchestrator: AIOrchestrator) -> None:
        self._orchestrator = orchestrator

    def generate(
        self,
        profile: MasterProfile,
        recommendation: Recommendation,
        company: str = "",
        recipient: str = "",
    ) -> CoverLetter:
        matched = recommendation.matched_detail.matched_skills
        edu_lines = "\n".join(
            f"- {e.degree or ''} in {e.field_of_study or ''} at {e.institution}"
            for e in profile.education
        )
        exp_lines = "\n".join(
            f"- {e.title or ''} at {e.company or ''}"
            for e in profile.experience
        )

        variables = {
            "candidate_name": profile.personal_info.full_name,
            "job_title": str(recommendation.job_id),
            "company": company,
            "recipient": recipient or "Hiring Manager",
            "matched_skills": ", ".join(matched) or "none",
            "education": edu_lines or "none",
            "experience": exp_lines or "none",
        }

        body = self._orchestrator.generate_text(
            prompt_name="cover_letter",
            variables=variables,
            feature=AIFeature.COVER_LETTER,
        )

        return CoverLetter(
            body=body,
            recipient_name=recipient or None,
            company_name=company or None,
        )
