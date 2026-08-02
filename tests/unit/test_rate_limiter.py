from __future__ import annotations

import time
from unittest.mock import patch

from app.infrastructure.job_sources.rate_limiter import RateLimiter


def test_rate_limiter_allows_immediate_first_call() -> None:
    """The first call should not wait when no request has been made."""
    limiter = RateLimiter(min_interval_seconds=1.0)

    started = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - started

    assert elapsed < 0.5


def test_rate_limiter_enforces_minimum_interval() -> None:
    """A second call within the interval should be throttled."""
    limiter = RateLimiter(min_interval_seconds=0.5)
    limiter.wait()

    started = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - started

    assert elapsed >= 0.4


def test_rate_limiter_zero_interval_never_waits() -> None:
    """A zero interval should never block."""
    limiter = RateLimiter(min_interval_seconds=0.0)
    with patch("time.monotonic", side_effect=[100.0, 100.0]):
        limiter.wait()
        limiter.wait()
