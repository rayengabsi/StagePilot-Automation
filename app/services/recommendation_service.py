from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.matching import MatchingConfig, get_matching_config
from app.db.models.jobs import Job
from app.db.models.matching import JobMatch
from app.db.models.profile import Profile as ProfileRecord
from app.db.models.recommendation import RecommendationFeedbackRecord, RecommendationRecord
from app.domain.master_profile.entities import MasterProfile
from app.domain.master_profile.errors import ProfileNotFoundError
from app.domain.recommendation.aggregator import ScoreAggregator
from app.domain.recommendation.entities import (
    HardRuleResult,
    MatchedDetail,
    Recommendation,
    RecommendationFeedback,
    ScoreBreakdown,
)
from app.domain.recommendation.enums import FeedbackReason, RecommendationStatus
from app.domain.recommendation.errors import ProfileNotReadyError
from app.domain.recommendation.matcher import HardRuleMatcher
from app.domain.recommendation.profile_matcher import ProfileMatcher
from app.domain.recommendation.scorer import SimilarityScorer


class RecommendationService:
    """Orchestrate the full recommendation pipeline.

    Loads the master profile, matches against qualified jobs,
    ranks recommendations, persists them, and provides feedback support.
    """

    def __init__(
        self,
        session: Session,
        config: MatchingConfig | None = None,
    ) -> None:
        self._session = session
        self._config = config or get_matching_config()
        self._matcher = ProfileMatcher(
            config=self._config,
            hard_rule_matcher=HardRuleMatcher(self._config),
            scorer=SimilarityScorer(self._config),
            aggregator=ScoreAggregator(self._config),
        )

    def recommend(
        self,
        top_n: int | None = None,
        profile_id: int | None = None,
    ) -> list[Recommendation]:
        profile_rec, domain_profile = self._load_profile(profile_id)

        cutoff = self._config.thresholds.get("recommendation_cutoff", 0.0)
        jobs = self._load_jobs()

        results: list[Recommendation] = []
        for job in jobs:
            rec = self._matcher.match(domain_profile, job, profile_rec.id)
            if rec.final_score >= cutoff or rec.status == RecommendationStatus.ACTIVE:
                results.append(rec)

        results.sort(key=lambda r: r.final_score, reverse=True)

        ranked: list[Recommendation] = []
        for pos, rec in enumerate(results, start=1):
            ranked.append(
                Recommendation(
                    profile_id=rec.profile_id,
                    job_id=rec.job_id,
                    final_score=rec.final_score,
                    ranking_position=pos,
                    status=rec.status,
                    matched_detail=rec.matched_detail,
                    score_breakdown=rec.score_breakdown,
                    hard_rule_result=rec.hard_rule_result,
                    created_at=rec.created_at,
                )
            )

        self._persist_recommendations(ranked)

        if top_n is not None:
            return ranked[:top_n]
        return ranked

    def feedback(
        self,
        recommendation_id: int,
        reason: str,
        comment: str | None = None,
    ) -> RecommendationFeedback:
        record = RecommendationFeedbackRecord(
            recommendation_id=recommendation_id,
            reason=reason,
            comment=comment,
        )
        self._session.add(record)
        self._session.flush()
        return RecommendationFeedback(
            recommendation_id=recommendation_id,
            reason=FeedbackReason(reason),
            comment=comment,
            created_at=str(record.created_at),
        )

    def list_recommendations(
        self,
        top_n: int | None = None,
        status: str | None = None,
    ) -> list[Recommendation]:
        query = self._session.query(RecommendationRecord).order_by(
            RecommendationRecord.ranking_position
        )
        if status:
            query = query.filter(RecommendationRecord.status == status)
        if top_n:
            query = query.limit(top_n)
        records = query.all()
        return [self._record_to_domain(r) for r in records]

    def _load_profile(
        self, profile_id: int | None = None
    ) -> tuple[ProfileRecord, MasterProfile]:
        from app.services.profile_service import ProfileService

        ps = ProfileService
        temp_service = ps(session=self._session, parser=None, normalizer=None, validator=None)
        try:
            domain_profile = temp_service.get_current_profile()
        except ProfileNotFoundError as e:
            raise ProfileNotReadyError("No master profile found. Import a resume first.") from e

        if profile_id is None:
            stmt = select(ProfileRecord).order_by(ProfileRecord.id.desc()).limit(1)
            profile_rec = self._session.scalar(stmt)
        else:
            profile_rec = self._session.get(ProfileRecord, profile_id)
        if profile_rec is None:
            raise ProfileNotFoundError("Profile record not found")
        if domain_profile is None:
            from app.services.profile_service import ProfileService
            ps = ProfileService
            temp = ps(session=self._session, parser=None, normalizer=None, validator=None)
            domain_profile = temp.get_current_profile()

        return profile_rec, domain_profile

    def _load_jobs(self) -> list[Job]:
        subq = (
            select(JobMatch.job_id)
            .where(JobMatch.hard_filter_ok.is_(True))
            .subquery()
        )
        stmt = select(Job).where(Job.id.in_(select(subq.c.job_id)))
        result = self._session.execute(stmt).scalars().all()
        return list(result)

    def _persist_recommendations(self, recommendations: list[Recommendation]) -> None:
        for rec in recommendations:
            record = RecommendationRecord(
                profile_id=rec.profile_id,
                job_id=rec.job_id,
                final_score=rec.final_score,
                ranking_position=rec.ranking_position,
                status=rec.status.value,
                matched_skills_json=list(rec.matched_detail.matched_skills),
                missing_skills_json=list(rec.matched_detail.missing_skills),
                matched_technologies_json=list(rec.matched_detail.matched_technologies),
                missing_technologies_json=list(rec.matched_detail.missing_technologies),
                matched_preferences_json=list(rec.matched_detail.matched_preferences),
                unmatched_preferences_json=list(rec.matched_detail.unmatched_preferences),
                score_breakdown_json=rec.score_breakdown.to_dict(),
                hard_rule_passed=rec.hard_rule_result.passed,
                hard_rule_reasons=list(rec.hard_rule_result.reasons),
            )
            self._session.add(record)
        self._session.flush()

    @staticmethod
    def _record_to_domain(r: RecommendationRecord) -> Recommendation:
        return Recommendation(
            profile_id=r.profile_id,
            job_id=r.job_id,
            final_score=r.final_score,
            ranking_position=r.ranking_position,
            status=RecommendationStatus(r.status),
            matched_detail=MatchedDetail(
                matched_skills=tuple(r.matched_skills_json or []),
                missing_skills=tuple(r.missing_skills_json or []),
                matched_technologies=tuple(r.matched_technologies_json or []),
                missing_technologies=tuple(r.missing_technologies_json or []),
                matched_preferences=tuple(r.matched_preferences_json or []),
                unmatched_preferences=tuple(r.unmatched_preferences_json or []),
            ),
            score_breakdown=ScoreBreakdown(
                **(r.score_breakdown_json or {})
            ),
            hard_rule_result=HardRuleResult(
                passed=r.hard_rule_passed,
                reasons=tuple(r.hard_rule_reasons or []),
            ),
            created_at=str(r.created_at) if r.created_at else "",
        )
