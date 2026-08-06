"""Unit tests for structured stage logging in the LinkedIn pipeline."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock

from app.domain.jobs.errors import LinkedInSessionExpiredError
from app.infrastructure.linkedin_mcp.stage_logging import (
    JsonStageLogger,
    QuietStageLogger,
)
from app.services.linkedin_mcp_pipeline_service import (
    LinkedInMCPPipelineResult,
)
from app.services.linkedin_notify_service import LinkedInNotifyService


class _FakeStage:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, dict[str, object]]] = []

    def stage(self, name: str, status: str = "ok", **fields: object) -> None:
        self.records.append((name, status, fields))


def test_json_stage_logger_emits_one_json_line_per_stage() -> None:
    lines: list[str] = []
    logger = JsonStageLogger(emit=lambda line: lines.append(line), run_id="run-1")
    logger.stage("fetch", status="ok", fetched=3)
    logger.stage("deliver", status="ok", sent=1)

    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event"] == "stage"
    assert first["stage"] == "fetch"
    assert first["status"] == "ok"
    assert first["fetched"] == 3
    assert first["run_id"] == "run-1"
    assert "ts" in first


def test_json_stage_logger_coerces_datetime_and_objects() -> None:
    lines: list[str] = []
    logger = JsonStageLogger(emit=lambda line: lines.append(line))
    logger.stage("x", posted_at=datetime(2026, 8, 1), obj=object())

    record = json.loads(lines[0])
    assert record["posted_at"].startswith("2026-08-01")
    assert isinstance(record["obj"], str)


def test_quiet_stage_logger_discards_records() -> None:
    QuietStageLogger().stage("fetch", status="ok", fetched=1)  # must not raise


def test_notify_records_stages_ok() -> None:
    pipeline = MagicMock()
    pipeline.run.return_value = LinkedInMCPPipelineResult(
        source_id=1,
        source_name="linkedin-mcp",
        cutoff=30.0,
        fetched=2,
        inserted=2,
        duplicates=0,
        rejected=0,
        matched_total=0,
        above_threshold=0,
        below_threshold=0,
        recommendations=(),
    )
    stages = _FakeStage()
    service = LinkedInNotifyService(
        session=MagicMock(),
        settings=MagicMock(),
        state_repo=MagicMock(),
        notifier=MagicMock(),
        pipeline=pipeline,
        stage_logger=stages,
    )

    service.run()

    assert [name for name, _, _ in stages.records] == ["start", "fetch", "deliver", "summary"]


def test_notify_records_auth_required_stage() -> None:
    pipeline = MagicMock()
    pipeline.run.side_effect = LinkedInSessionExpiredError("login required")
    stages = _FakeStage()
    service = LinkedInNotifyService(
        session=MagicMock(),
        settings=MagicMock(),
        state_repo=MagicMock(),
        notifier=MagicMock(),
        pipeline=pipeline,
        stage_logger=stages,
    )

    result = service.run()

    assert result.status == "auth_required"
    assert ("auth", "auth_required", {}) in stages.records
