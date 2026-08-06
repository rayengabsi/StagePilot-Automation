"""Unit tests for the LinkedIn end-to-end notify service.

Uses injected pipeline/notifier/state-repo mocks so no MCP subprocess, database,
or Telegram network is touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.domain.jobs.errors import LinkedInSessionExpiredError
from app.infrastructure.linkedin_mcp.notification_state import (
    JsonNotificationStateRepository,
    NotificationStateRepository,
)
from app.services.linkedin_mcp_pipeline_service import (
    LinkedInMCPPipelineResult,
    LinkedInMCPRecommendationResult,
)
from app.services.linkedin_notify_service import LinkedInNotifyService


def test_json_state_repository_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "notified.json"
    repo = JsonNotificationStateRepository(path)
    assert repo.is_notified("https://x/1/") is False

    repo.mark_notified("https://x/1/")
    repo.mark_notified("https://x/1/")

    loaded = JsonNotificationStateRepository(path)
    assert loaded.is_notified("https://x/1/") is True
    assert loaded.is_notified("https://x/2/") is False
    assert json.loads(path.read_text(encoding="utf-8")) == {"notified": ["https://x/1/"]}


def _recommendation(
    *,
    url: str = "https://www.linkedin.com/jobs/view/101/",
    above: bool = True,
) -> LinkedInMCPRecommendationResult:
    return LinkedInMCPRecommendationResult(
        job_id=101,
        title="Software Engineer Intern",
        company="Acme Tech",
        location="Tunis, Tunisia",
        url=url,
        final_score=62.0,
        status="active",
        above_threshold=above,
        explanation="Python aligns with your profile.",
        matched_skills=("Python",),
        missing_skills=(),
    )


def _pipeline_result(*recs: LinkedInMCPRecommendationResult) -> LinkedInMCPPipelineResult:
    above = sum(1 for r in recs if r.above_threshold)
    return LinkedInMCPPipelineResult(
        source_id=1,
        source_name="linkedin-mcp",
        cutoff=30.0,
        fetched=2,
        inserted=2,
        duplicates=0,
        rejected=0,
        matched_total=len(recs),
        above_threshold=above,
        below_threshold=len(recs) - above,
        recommendations=tuple(recs),
    )


class _FakeNotifier:
    def __init__(self) -> None:
        self.received: list[LinkedInMCPRecommendationResult] = []

    def send_linkedin_matches(self, recommendations: list[LinkedInMCPRecommendationResult]) -> int:
        self.received.extend(recommendations)
        return len(recommendations)


class _FakeState(NotificationStateRepository):
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_notified(self, job_identifier: str) -> bool:
        return job_identifier in self._seen

    def mark_notified(self, job_identifier: str) -> None:
        self._seen.add(job_identifier)


def _service(
    pipeline_result: object, *, state: _FakeState
) -> tuple[LinkedInNotifyService, _FakeNotifier, _FakeState]:
    pipeline = MagicMock()
    pipeline.run.return_value = pipeline_result
    notifier = _FakeNotifier()
    service = LinkedInNotifyService(
        session=MagicMock(),
        settings=MagicMock(),
        state_repo=state,
        notifier=notifier,  # type: ignore[arg-type]
        pipeline=pipeline,
    )
    return service, notifier, state


def test_notify_reports_auth_required_when_session_expired() -> None:
    pipeline = MagicMock()
    pipeline.run.side_effect = LinkedInSessionExpiredError("Not logged in")
    service = LinkedInNotifyService(
        session=MagicMock(),
        settings=MagicMock(),
        state_repo=_FakeState(),
        notifier=_FakeNotifier(),  # type: ignore[arg-type]
        pipeline=pipeline,
    )

    result = service.run()

    assert result.status == "auth_required"
    assert "login" in (result.message or "").lower()


def test_notify_reports_error_when_pipeline_fails() -> None:
    pipeline = MagicMock()
    pipeline.run.side_effect = RuntimeError("boom")
    service = LinkedInNotifyService(
        session=MagicMock(),
        settings=MagicMock(),
        state_repo=_FakeState(),
        notifier=_FakeNotifier(),  # type: ignore[arg-type]
        pipeline=pipeline,
    )

    result = service.run()

    assert result.status == "error"
    assert result.message == "boom"


def test_notify_delivers_then_deduplicates() -> None:
    service, notifier, state = _service(_pipeline_result(_recommendation()), state=_FakeState())
    first = service.run()
    assert first.status == "ok"
    assert first.new_matches == 1
    assert first.telegram_sent == 1
    assert len(notifier.received) == 1
    assert state.is_notified("https://www.linkedin.com/jobs/view/101/")

    second = service.run()
    assert second.status == "ok"
    assert second.already_notified == 1
    assert second.new_matches == 0
    assert second.telegram_sent == 0
    assert len(notifier.received) == 1


def test_notify_only_passes_above_threshold_matches() -> None:
    pipeline_result = _pipeline_result(
        _recommendation(url="https://x/above/"),
        _recommendation(url="https://x/below/", above=False),
    )
    service, notifier, _ = _service(pipeline_result, state=_FakeState())

    result = service.run()

    assert result.status == "ok"
    assert result.above_threshold == 1
    assert [rec.url for rec in notifier.received] == ["https://x/above/"]


def _get_sent_urls(notifier: _FakeNotifier) -> list[str]:
    return [rec.url for rec in notifier.received]
