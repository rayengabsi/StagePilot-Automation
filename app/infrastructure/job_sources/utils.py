from __future__ import annotations

import re
from datetime import UTC, datetime

_WHITESPACE_RE = re.compile(r"\s+")


def parse_datetime(value: str | int | None) -> datetime | None:
    """Parse a common ISO-8601 or RFC-2822 datetime string."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return _from_epoch_seconds(float(value))
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def parse_epoch_millis(value: int | None) -> datetime | None:
    """Convert a Unix epoch milliseconds value to a UTC datetime."""
    if value is None:
        return None
    return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)


def clean_text(value: str | None) -> str | None:
    """Collapse whitespace and trim; return None for blank strings."""
    if not value:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", value).strip()
    return cleaned or None


def strip_html(value: str | None) -> str | None:
    """Strip HTML tags from a string and normalize whitespace."""
    if not value:
        return None
    from bs4 import BeautifulSoup

    text = BeautifulSoup(value, "html.parser").get_text(" ")
    return clean_text(text)


def _from_epoch_seconds(epoch: float) -> datetime:
    """Convert a Unix epoch seconds value to a UTC datetime."""
    return datetime.fromtimestamp(epoch, tz=UTC)
