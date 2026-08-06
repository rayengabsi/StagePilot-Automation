from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import final


class NotificationStateRepository(ABC):
    """Tracks which LinkedIn jobs were already notified.

    The notification pipeline depends only on this interface so the JSON file
    implementation can be swapped for a database-backed one without touching
    the business logic.
    """

    @abstractmethod
    def is_notified(self, job_identifier: str) -> bool:
        """Return True if the job was already delivered to Telegram."""

    @abstractmethod
    def mark_notified(self, job_identifier: str) -> None:
        """Record that the job was delivered to Telegram."""


@final
class JsonNotificationStateRepository(NotificationStateRepository):
    """Persists the notified-set in a small gitignored JSON file.

    The file stores ``{"notified": ["<job-id>", ...]}``. Writes are atomic so
    a crash never corrupts the set. File access stays behind this class.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._notified: set[str] | None = None

    def is_notified(self, job_identifier: str) -> bool:
        return job_identifier in self._load()

    def mark_notified(self, job_identifier: str) -> None:
        notified = self._load()
        if job_identifier in notified:
            return
        notified.add(job_identifier)
        self._save(notified)

    def _load(self) -> set[str]:
        if self._notified is not None:
            return self._notified
        notified: set[str] = set()
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                raw = data.get("notified", []) if isinstance(data, dict) else []
                notified = {str(item) for item in raw if item is not None}
            except (json.JSONDecodeError, OSError):
                notified = set()
        self._notified = notified
        return notified

    def _save(self, notified: set[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"notified": sorted(notified)}, indent=2)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self._path)
