from __future__ import annotations

from app.domain.ai.entities import ExplanationResult
from app.domain.ai.enums import AIFeature
from app.domain.recommendation.entities import Recommendation
from app.services.ai_orchestrator import AIOrchestrator


class ExplanationService:
    """Generate natural-language explanations for recommendations.

    The AI receives structured match data and produces human-readable text.
    Python determines the facts; AI only rewrites them.
    """

    def __init__(self, orchestrator: AIOrchestrator) -> None:
        self._orchestrator = orchestrator

    def explain(
        self,
        recommendation: Recommendation,
        job_title: str = "",
        company: str = "",
    ) -> ExplanationResult:
        """Generate a natural-language explanation for one recommendation."""
        if not job_title:
            job_title = f"Job #{recommendation.job_id}"

        variables = {
            "job_title": job_title,
            "company": company,
            "final_score": f"{recommendation.final_score:.1f}",
            "matched_skills": ", ".join(recommendation.matched_detail.matched_skills) or "none",
            "missing_skills": ", ".join(recommendation.matched_detail.missing_skills) or "none",
            "matched_technologies": ", ".join(
                recommendation.matched_detail.matched_technologies
            ) or "none",
            "missing_technologies": ", ".join(
                recommendation.matched_detail.missing_technologies
            ) or "none",
            "score_breakdown": str(dict(recommendation.score_breakdown.to_dict())),
            "hard_rule_result": (
                "passed" if recommendation.hard_rule_result.passed
                else f"failed: {', '.join(recommendation.hard_rule_result.reasons)}"
            ),
        }

        text = self._orchestrator.generate_text(
            prompt_name="match_explanation",
            variables=variables,
            feature=AIFeature.EXPLANATION,
        )

        return ExplanationResult(
            explanation=text,
            recommendation_id=recommendation.job_id,
        )
