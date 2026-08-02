from __future__ import annotations

import time


class RateLimiter:
    """Enforce a minimum interval between provider requests.

    Prevents accidental abuse of third-party APIs during paginated discovery.
    """

    def __init__(self, min_interval_seconds: float = 0.0) -> None:
        """Initialize the rate limiter with a minimum interval."""
        self._min_interval = max(0.0, min_interval_seconds)
        self._last_request_at = 0.0

    @property
    def min_interval_seconds(self) -> float:
        """Return the configured minimum interval between requests."""
        return self._min_interval

    def wait(self) -> None:
        """Sleep as needed to respect the minimum interval."""
        if self._min_interval <= 0.0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if self._last_request_at and elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()
