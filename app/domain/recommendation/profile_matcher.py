from __future__ import annotations

from app.config.matching import MatchingConfig
from app.db.models.jobs import Job
from app.domain.master_profile.entities import MasterProfile
from app.domain.recommendation.aggregator import ScoreAggregator
from app.domain.recommendation.entities import (
    MatchedDetail,
    Recommendation,
    ScoreBreakdown,
)
from app.domain.recommendation.enums import RecommendationStatus
from app.domain.recommendation.matcher import HardRuleMatcher
from app.domain.recommendation.scorer import SimilarityScorer


class ProfileMatcher:
    """Orchestrate the full matching pipeline for one profile against one job."""

    def __init__(
        self,
        config: MatchingConfig,
        hard_rule_matcher: HardRuleMatcher,
        scorer: SimilarityScorer,
        aggregator: ScoreAggregator,
    ) -> None:
        self._config = config
        self._hard_rule_matcher = hard_rule_matcher
        self._scorer = scorer
        self._aggregator = aggregator

    def match(
        self,
        profile: MasterProfile,
        job: Job,
        profile_id: int,
        ranking_position: int = 0,
    ) -> Recommendation:
        hard_result = self._hard_rule_matcher.evaluate(profile, job)

        if not hard_result.passed:
            return Recommendation(
                profile_id=profile_id,
                job_id=job.id,
                final_score=0.0,
                ranking_position=ranking_position,
                status=RecommendationStatus.REJECTED,
                matched_detail=MatchedDetail(),
                score_breakdown=ScoreBreakdown(),
                hard_rule_result=hard_result,
            )

        category_scores = self._scorer.score_all(profile, job)
        matched = self._scorer.match_detail(profile, job)
        final_score = self._aggregator.aggregate(category_scores)

        threshold = self._config.thresholds.get("recommendation_cutoff", 0.0)
        status = (
            RecommendationStatus.ACTIVE
            if final_score >= threshold
            else RecommendationStatus.REJECTED
        )

        return Recommendation(
            profile_id=profile_id,
            job_id=job.id,
            final_score=final_score,
            ranking_position=ranking_position,
            status=status,
            matched_detail=matched,
            score_breakdown=category_scores,
            hard_rule_result=hard_result,
        )
