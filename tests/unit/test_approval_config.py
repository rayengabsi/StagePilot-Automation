from __future__ import annotations

from app.config.approval_config import ApprovalConfig, get_approval_config
from app.domain.approval.enums import QueueStrategy


def test_approval_config_defaults() -> None:
    config = ApprovalConfig()
    assert config.queue_strategy == QueueStrategy.FIFO
    assert config.queue_limit == 50
    assert config.approval_timeout_hours == 48
    assert config.auto_archive_days == 30
    assert config.config_version == "1.0.0"
    assert config.notifications_enabled is True


def test_approval_config_from_dict() -> None:
    config = ApprovalConfig.from_dict(
        {
            "queue": {
                "strategy": "highest_score",
                "limit": 100,
                "approval_timeout_hours": 24,
                "auto_archive_days": 7,
            },
            "priority": {"default": 5, "high": 20, "urgent": 200},
            "snapshot": {"config_version": "2.0.0"},
            "notifications": {"enabled": False, "on_approve": False},
        }
    )
    assert config.queue_strategy == QueueStrategy.HIGHEST_SCORE
    assert config.queue_limit == 100
    assert config.approval_timeout_hours == 24
    assert config.auto_archive_days == 7
    assert config.default_priority == 5
    assert config.high_priority == 20
    assert config.urgent_priority == 200
    assert config.config_version == "2.0.0"
    assert config.notifications_enabled is False
    assert config.notify_on_approve is False
    assert config.notify_on_reject is True


def test_get_approval_config_returns_instance() -> None:
    config = get_approval_config()
    assert isinstance(config, ApprovalConfig)
