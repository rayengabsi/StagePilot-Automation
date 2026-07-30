from __future__ import annotations

import email.utils
from datetime import UTC, datetime

import defusedxml.ElementTree as ET  # noqa: N817
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import Settings
from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceFetchError, SourceParseError
from app.shared.time import utc_now


class RssFeedConnector:
    """Fetch job listings from RSS or Atom feeds."""

    source_type = JobSourceType.RSS_FEED

    def __init__(self, settings: Settings) -> None:
        """Initialize the connector with HTTP configuration."""
        self._settings = settings

    def fetch(self, source: JobSourceConfig) -> list[DiscoveredJob]:
        """Fetch and parse RSS or Atom jobs from a configured source."""
        xml_text = self._fetch_xml(source)
        return self._parse_xml(source, xml_text)

    def _fetch_xml(self, source: JobSourceConfig) -> str:
        """Fetch XML content from a source URL."""
        retrying_fetch = retry(
            retry=retry_if_exception_type(
                (requests.Timeout, requests.ConnectionError, SourceFetchError)
            ),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            stop=stop_after_attempt(self._settings.discovery_retry_attempts),
            reraise=True,
        )(self._request_once)
        try:
            return retrying_fetch(source)
        except requests.RequestException as exc:
            raise SourceFetchError(f"Failed to fetch source '{source.name}'.") from exc

    def _request_once(self, source: JobSourceConfig) -> str:
        """Perform one HTTP request for a feed source."""
        response = requests.get(
            source.base_url,
            headers={"User-Agent": self._settings.discovery_user_agent},
            timeout=self._settings.discovery_http_timeout_seconds,
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise SourceFetchError(f"Temporary source HTTP failure: {response.status_code}")
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise SourceFetchError(f"Source returned HTTP {response.status_code}.") from exc
        return response.text

    def _parse_xml(self, source: JobSourceConfig, xml_text: str) -> list[DiscoveredJob]:
        """Parse RSS or Atom XML into discovered jobs."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise SourceParseError(f"Source '{source.name}' returned invalid XML.") from exc

        if self._strip_namespace(root.tag) == "rss":
            return self._parse_rss(source, root)
        if self._strip_namespace(root.tag) == "feed":
            return self._parse_atom(source, root)
        raise SourceParseError(f"Unsupported feed format for source '{source.name}'.")

    def _parse_rss(self, source: JobSourceConfig, root: ET.Element) -> list[DiscoveredJob]:
        """Parse RSS 2.0 feed items."""
        items = root.findall("./channel/item")
        return [job for item in items if (job := self._rss_item_to_job(source, item)) is not None]

    def _parse_atom(self, source: JobSourceConfig, root: ET.Element) -> list[DiscoveredJob]:
        """Parse Atom feed entries."""
        entries = [child for child in root if self._strip_namespace(child.tag) == "entry"]
        return [
            job for entry in entries if (job := self._atom_entry_to_job(source, entry)) is not None
        ]

    def _rss_item_to_job(self, source: JobSourceConfig, item: ET.Element) -> DiscoveredJob | None:
        """Convert one RSS item into a discovered job."""
        title = self._child_text(item, "title")
        link = self._child_text(item, "link")
        if not title or not link:
            return None

        external_id = self._child_text(item, "guid") or link
        description = self._child_text(item, "description")
        return DiscoveredJob(
            external_id=external_id,
            url=link,
            title=title,
            company=source.config.get("company") or source.name,
            location=source.config.get("default_location"),
            description=description,
            raw_payload={
                "title": title,
                "link": link,
                "guid": external_id,
                "description": description,
                "pubDate": self._child_text(item, "pubDate"),
            },
            discovered_at=utc_now(),
            posted_at=self._parse_datetime(self._child_text(item, "pubDate")),
        )

    def _atom_entry_to_job(
        self, source: JobSourceConfig, entry: ET.Element
    ) -> DiscoveredJob | None:
        """Convert one Atom entry into a discovered job."""
        title = self._child_text(entry, "title")
        link = self._atom_link(entry)
        if not title or not link:
            return None

        external_id = self._child_text(entry, "id") or link
        summary = self._child_text(entry, "summary") or self._child_text(entry, "content")
        updated = self._child_text(entry, "updated") or self._child_text(entry, "published")
        return DiscoveredJob(
            external_id=external_id,
            url=link,
            title=title,
            company=source.config.get("company") or source.name,
            location=source.config.get("default_location"),
            description=summary,
            raw_payload={
                "id": external_id,
                "title": title,
                "link": link,
                "summary": summary,
                "updated": updated,
            },
            discovered_at=utc_now(),
            posted_at=self._parse_datetime(updated),
        )

    def _child_text(self, element: ET.Element, child_name: str) -> str | None:
        """Return text from a child element, ignoring XML namespaces."""
        for child in element:
            if self._strip_namespace(child.tag) == child_name and child.text:
                return child.text.strip()
        return None

    def _atom_link(self, entry: ET.Element) -> str | None:
        """Return the best link URL for an Atom entry."""
        for child in entry:
            if self._strip_namespace(child.tag) == "link":
                href = child.attrib.get("href")
                if href:
                    return href.strip()
                if child.text:
                    return child.text.strip()
        return None

    def _strip_namespace(self, tag: str) -> str:
        """Remove an XML namespace from a tag name."""
        return tag.rsplit("}", maxsplit=1)[-1]

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse common RSS or Atom datetime strings."""
        if not value:
            return None
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            parsed = None
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
