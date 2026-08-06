from __future__ import annotations

from enum import StrEnum


class JobSourceType(StrEnum):
    """Supported external job source connector types."""

    RSS_FEED = "rss_feed"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    SMART_RECRUITERS = "smart_recruiters"
    TEAMTAILOR = "teamtailor"
    WELCOME_TO_THE_JUNGLE = "welcome_to_the_jungle"
    REMOTE_OK = "remote_ok"
    WELLFOUND = "wellfound"
    COMPANY_PAGES = "company_pages"
    LINKEDIN_MCP = "linkedin_mcp"
