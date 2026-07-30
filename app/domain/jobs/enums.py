from __future__ import annotations

from enum import StrEnum


class JobSourceType(StrEnum):
    """Supported external job source connector types."""

    RSS_FEED = "rss_feed"
