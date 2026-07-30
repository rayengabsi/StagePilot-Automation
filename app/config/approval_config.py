from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.domain.approval.enums import QueueStrategy


@dataclass(frozen=True, slots=True)
class ApprovalConfig:
    queue_strategy: QueueStrategy = QueueStrategy.FIFO
    queue_limit: int = 50
    approval_timeout_hours: int = 48
    auto_archive_days: int = 30
    default_priority: int = 0
    high_priority: int = 10
    urgent_priority: int = 100
    config_version: str = "1.0.0"
    notifications_enabled: bool = True
    notify_on_approve: bool = True
    notify_on_reject: bool = True
    notify_on_revision: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalConfig:
        queue = data.get("queue", {})
        priority = data.get("priority", {})
        snapshot = data.get("snapshot", {})
        notifications = data.get("notifications", {})
        return cls(
            queue_strategy=QueueStrategy(queue.get("strategy", "fifo")),
            queue_limit=queue.get("limit", 50),
            approval_timeout_hours=queue.get("approval_timeout_hours", 48),
            auto_archive_days=queue.get("auto_archive_days", 30),
            default_priority=priority.get("default", 0),
            high_priority=priority.get("high", 10),
            urgent_priority=priority.get("urgent", 100),
            config_version=snapshot.get("config_version", "1.0.0"),
            notifications_enabled=notifications.get("enabled", True),
            notify_on_approve=notifications.get("on_approve", True),
            notify_on_reject=notifications.get("on_reject", True),
            notify_on_revision=notifications.get("on_revision", True),
        )


@lru_cache
def get_approval_config() -> ApprovalConfig:
    """Load approval configuration from config/approval.toml."""
    config_path = Path("config/approval.toml")
    if config_path.exists():
        raw = config_path.read_text(encoding="utf-8")
        data: dict[str, Any] = tomllib.loads(raw)
        return ApprovalConfig.from_dict(data)
    return ApprovalConfig()
