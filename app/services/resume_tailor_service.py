from __future__ import annotations

import json

from app.domain.ai.entities import TailoredResume
from app.domain.ai.enums import AIFeature
from app.domain.master_profile.entities import MasterProfile
from app.domain.recommendation.entities import Recommendation
from app.services.ai_orchestrator import AIOrchestrator


class ResumeTailorService:
    """Tailor a resume for a specific job using AI.

    The AI may reorder skills, emphasize projects, and rewrite bullet points.
    It must NOT invent any experience, degrees, skills, or dates.
    """

    def __init__(self, orchestrator: AIOrchestrator) -> None:
        self._orchestrator = orchestrator

    def tailor(
        self,
        profile: MasterProfile,
        recommendation: Recommendation,
        job_description: str = "",
    ) -> TailoredResume:
        profile_json = json.dumps(profile.to_dict(), indent=2)
        variables = {
            "profile_json": profile_json,
            "job_title": str(recommendation.job_id),
            "job_description": job_description,
            "matched_skills": ", ".join(recommendation.matched_detail.matched_skills) or "none",
            "missing_skills": ", ".join(recommendation.matched_detail.missing_skills) or "none",
        }

        data = self._orchestrator.generate_json(
            prompt_name="resume_tailoring",
            variables=variables,
            feature=AIFeature.RESUME_TAILORING,
            required_fields=["summary", "skills", "experience", "projects"],
        )

        sections: dict[str, str] = {}
        for key in ("summary", "skills", "experience", "projects"):
            val = data.get(key)
            sections[key] = str(val) if val is not None else ""

        return TailoredResume(
            sections=sections,
            source_profile_version="current",
        )
