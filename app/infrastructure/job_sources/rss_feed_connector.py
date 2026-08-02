from __future__ import annotations

import email.utils
from datetime import UTC, datetime
from typing import Any, ClassVar

import defusedxml.ElementTree as ET  # noqa: N817

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.domain.jobs.errors import SourceParseError
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.shared.time import utc_now


class RssFeedConnector(BaseJobSourceConnector):
    """Fetch job listings from RSS or Atom feeds."""

    source_type: ClassVar[JobSourceType] = JobSourceType.RSS_FEED
    provider_name: ClassVar[str] = "rss"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that an RSS source has a fetchable URL."""
        return super().validate(source)

    def _fetch_page(self, source: JobSourceConfig, cursor: Any) -> PageResult:  # noqa: ANN401, ARG002
        """Fetch and parse a single feed into raw item dicts."""
        xml_text = self._http.get_text(
            source.base_url,
            headers={"User-Agent": self._settings.discovery_user_agent},
        )
        items = self._parse_xml_items(source, xml_text)
        return PageResult(items=items, next_cursor=None)

    def _parse_xml_items(self, source: JobSourceConfig, xml_text: str) -> list[dict[str, Any]]:
        """Parse RSS or Atom XML into raw item dictionaries."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise SourceParseError(f"Source '{source.name}' returned invalid XML.") from exc

        if self._strip_namespace(root.tag) == "rss":
            return self._parse_rss_items(source, root)
        if self._strip_namespace(root.tag) == "feed":
            return self._parse_atom_items(source, root)
        raise SourceParseError(f"Unsupported feed format for source '{source.name}'.")

    def _parse_rss_items(
        self, source: JobSourceConfig, root: ET.Element
    ) -> list[dict[str, Any]]:
        """Parse RSS 2.0 feed items into raw dictionaries."""
        items: list[dict[str, Any]] = []
        for item in root.findall("./channel/item"):
            raw = self._rss_item_to_raw(source, item)
            if raw is not None:
                items.append(raw)
        return items

    def _parse_atom_items(
        self, source: JobSourceConfig, root: ET.Element
    ) -> list[dict[str, Any]]:
        """Parse Atom feed entries into raw dictionaries."""
        items: list[dict[str, Any]] = []
        entries = [child for child in root if self._strip_namespace(child.tag) == "entry"]
        for entry in entries:
            raw = self._atom_entry_to_raw(source, entry)
            if raw is not None:
                items.append(raw)
        return items

    def _rss_item_to_raw(
        self, source: JobSourceConfig, item: ET.Element
    ) -> dict[str, Any] | None:
        """Convert one RSS item into a raw dictionary."""
        title = self._child_text(item, "title")
        link = self._child_text(item, "link")
        if not title or not link:
            return None

        external_id = self._child_text(item, "guid") or link
        description = self._child_text(item, "description")
        return {
            "external_id": external_id,
            "url": link,
            "title": title,
            "company": source.config.get("company") or source.name,
            "location": source.config.get("default_location"),
            "description": description,
            "posted_at": self._parse_datetime(self._child_text(item, "pubDate")),
            "raw_payload": {
                "title": title,
                "link": link,
                "guid": external_id,
                "description": description,
                "pubDate": self._child_text(item, "pubDate"),
            },
        }

    def _atom_entry_to_raw(
        self, source: JobSourceConfig, entry: ET.Element
    ) -> dict[str, Any] | None:
        """Convert one Atom entry into a raw dictionary."""
        title = self._child_text(entry, "title")
        link = self._atom_link(entry)
        if not title or not link:
            return None

        external_id = self._child_text(entry, "id") or link
        summary = self._child_text(entry, "summary") or self._child_text(entry, "content")
        updated = self._child_text(entry, "updated") or self._child_text(entry, "published")
        return {
            "external_id": external_id,
            "url": link,
            "title": title,
            "company": source.config.get("company") or source.name,
            "location": source.config.get("default_location"),
            "description": summary,
            "posted_at": self._parse_datetime(updated),
            "raw_payload": {
                "id": external_id,
                "title": title,
                "link": link,
                "summary": summary,
                "updated": updated,
            },
        }

    def normalize(self, raw: dict[str, Any], source: JobSourceConfig) -> DiscoveredJob | None:
        """Convert a raw feed item into a discovered job."""
        raw_payload = dict(raw.get("raw_payload") or {})
        return DiscoveredJob(
            external_id=raw.get("external_id"),
            url=raw["url"],
            title=raw["title"],
            company=raw.get("company") or source.name,
            location=raw.get("location"),
            description=raw.get("description"),
            raw_payload=raw_payload,
            discovered_at=utc_now(),
            posted_at=raw.get("posted_at"),
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
