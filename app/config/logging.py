from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging import LogRecord
from typing import Any

from app.config.settings import Settings


class JsonFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    _reserved_keys = frozenset(vars(logging.makeLogRecord({})))

    def format(self, record: LogRecord) -> str:
        """Format a log record into a JSON string."""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._reserved_keys and not key.startswith("_")
        }
        if extras:
            payload["extra"] = extras

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=True)


def configure_logging(settings: Settings) -> None:
    """Configure root logging for the application process."""
    handler = logging.StreamHandler()
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)
