from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

_WHITESPACE_RE = re.compile(r"\s+")


def parse_html(html: str) -> BeautifulSoup:
    """Parse HTML text into a BeautifulSoup document using the lxml parser."""
    return BeautifulSoup(html, "lxml")


def css_select(soup: BeautifulSoup, selector: str) -> list[Tag]:
    """Select elements from a document using a CSS selector."""
    return soup.select(selector)


def css_select_first(soup: BeautifulSoup, selector: str) -> Tag | None:
    """Return the first element matching a CSS selector, or None."""
    if not selector:
        return None
    return soup.select_one(selector)


def xpath_select(html: str, expression: str) -> list[Any]:
    """Evaluate an XPath expression against HTML text using lxml."""
    from lxml import etree

    parser = etree.HTMLParser()
    tree = etree.fromstring(html.encode("utf-8", errors="replace"), parser)
    if tree is None:
        return []
    return tree.xpath(expression)


def extract_metadata(soup: BeautifulSoup) -> dict[str, str]:
    """Extract meta tag properties and names from a document head."""
    metadata: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property")
        content = meta.get("content")
        if name and content:
            metadata[name] = content
    return metadata


def extract_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extract JSON-LD structured data blocks from a document."""
    blocks: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if not text or not text.strip():
            continue
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            blocks.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks


def extract_text(element: Tag | None) -> str | None:
    """Return normalized visible text from an element, or None."""
    if element is None:
        return None
    return _normalize_whitespace(element.get_text(" ")) or None


def extract_attr(element: Tag | None, attr: str) -> str | None:
    """Return an attribute value from an element, or None."""
    if element is None:
        return None
    value = element.get(attr)
    if value is None:
        return None
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    text = str(value).strip()
    return text or None


def extract_href(element: Tag | None, base_url: str) -> str | None:
    """Return an absolute href from an element, or None."""
    href = extract_attr(element, "href")
    if not href:
        return None
    return urljoin(base_url, href)


def resolve_url(url: str | None, base_url: str) -> str | None:
    """Resolve a possibly-relative URL against a base URL."""
    if not url:
        return None
    return urljoin(base_url, url)


def normalize_text(value: str | None) -> str | None:
    """Normalize whitespace and trim; return None for blank strings."""
    if not value:
        return None
    return _normalize_whitespace(value) or None


def _normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace into single spaces."""
    return _WHITESPACE_RE.sub(" ", value).strip()
