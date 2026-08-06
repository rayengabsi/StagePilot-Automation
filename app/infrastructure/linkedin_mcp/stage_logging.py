"""Structured, one-log-line-per-stage output for the LinkedIn pipeline.

The pipeline depends only on the ``LinkedInStageLogger`` port so it stays
decoupled from any concrete sink. A JSON-lines implementation is provided for
machine-readable, per-stage observability; the notify pipeline can be run with
``--verbose`` to see every stage emitted as one parseable JSON line.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.shared.time import utc_now


class LinkedInStageLogger(ABC):
    """Records one structured record per pipeline stage."""

    @abstractmethod
    def stage(
        self,
        name: str,
        status: str = "ok",
        **fields: object,
    ) -> None:
        """Emit a single structured stage record."""


class JsonStageLogger(LinkedInStageLogger):
    """Emit each stage as one JSON line via an injectable sink.

    The default sink is stdout. A ``run_id`` groups all stages of one run.
    """

    def __init__(
        self,
        emit: Callable[[str], None] | None = None,
        *,
        run_id: str | None = None,
    ) -> None:
        self._emit = emit or print
        self._run_id = run_id

    def stage(
        self,
        name: str,
        status: str = "ok",
        **fields: object,
    ) -> None:
        """Serialize one stage record to a single JSON line."""
        record: dict[str, Any] = {
            "ts": _iso(utc_now()),
            "event": "stage",
            "stage": name,
            "status": status,
            **{key: _jsonable(value) for key, value in fields.items()},
        }
        if self._run_id:
            record["run_id"] = self._run_id
        self._emit(json.dumps(record, separators=(",", ":"), ensure_ascii=True, default=str))


class QuietStageLogger(LinkedInStageLogger):
    """Accepts stage events but discards them (default = not verbose)."""

    def stage(
        self,
        _name: str,
        _status: str = "ok",
        **_fields: object,
    ) -> None:
        return None


def _jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=value.astimezone().tzinfo)
    return value.isoformat()
