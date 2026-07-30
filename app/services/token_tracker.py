from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models.ai_usage import TokenUsageRecord
from app.domain.ai.entities import TokenUsage
from app.domain.ai.enums import AIFeature
from app.domain.ai.errors import TokenTrackingError

_COST_PER_1K_INPUT_TOKENS: dict[str, float] = {
    "gemini-2.0-flash-lite": 0.075,
}


class TokenTracker:
    """Track and persist AI token usage for analytics and cost estimation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def track(
        self,
        provider: str,
        model: str,
        feature: AIFeature,
        prompt_version: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> TokenUsage:
        """Record a token usage entry and persist it."""
        cost = self._estimate_cost(model, input_tokens, output_tokens)
        now = datetime.now(UTC).isoformat()
        record = TokenUsageRecord(
            provider=provider,
            model=model,
            feature=feature.value,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=cost,
        )
        try:
            self._session.add(record)
            self._session.flush()
        except Exception as exc:
            raise TokenTrackingError(f"Failed to persist token usage: {exc}") from exc

        return TokenUsage(
            provider=provider,
            model=model,
            feature=feature,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=cost,
            created_at=now,
        )

    def get_usage(
        self,
        limit: int = 50,
        feature: str | None = None,
    ) -> list[TokenUsage]:
        """Retrieve recent token usage records."""
        query = self._session.query(TokenUsageRecord).order_by(TokenUsageRecord.created_at.desc())
        if feature:
            query = query.filter(TokenUsageRecord.feature == feature)
        records = query.limit(limit).all()
        return [
            TokenUsage(
                provider=r.provider,
                model=r.model,
                feature=AIFeature(r.feature),
                prompt_version=r.prompt_version,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                latency_ms=r.latency_ms,
                estimated_cost=r.estimated_cost,
                created_at=str(r.created_at),
            )
            for r in records
        ]

    @staticmethod
    def _estimate_cost(model: str, input_tokens: int, _output_tokens: int) -> float:
        """Estimate cost in USD based on input tokens."""
        rate = _COST_PER_1K_INPUT_TOKENS.get(model, 0.0)
        return round((input_tokens / 1000.0) * rate, 6)
