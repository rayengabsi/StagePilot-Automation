from __future__ import annotations

import hashlib
from typing import Any, ClassVar

from app.domain.jobs.entities import DiscoveredJob, JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.html.parsing import (
    css_select,
    css_select_first,
    extract_href,
    extract_json_ld,
    extract_text,
    parse_html,
)
from app.infrastructure.job_sources.base import BaseJobSourceConnector, PageResult
from app.infrastructure.job_sources.utils import clean_text
from app.shared.time import utc_now


class CompanyPagesConnector(BaseJobSourceConnector):
    """Scrape generic company career pages using configurable CSS selectors.

    Configuration keys (in ``source.config``):

    - ``list_url``: URL of the jobs listing page (defaults to ``base_url``).
    - ``job_links_selector``: CSS selector for anchors to individual job posts.
    - ``next_page_selector``: optional CSS selector for the pagination link.
    - ``title_selector``: optional CSS selector for the title on job pages.
    - ``description_selector``: optional CSS selector for the description body.
    - ``scrape_details``: fetch each job page (default ``true``).
    - ``max_pages``: maximum listing pages to crawl (default ``1``).
    """

    source_type: ClassVar[JobSourceType] = JobSourceType.COMPANY_PAGES
    provider_name: ClassVar[str] = "company_pages"

    def validate(self, source: JobSourceConfig) -> list[str]:
        """Validate that a job links selector is configured."""
        errors = super().validate(source)
        if not source.config.get("job_links_selector"):
            errors.append("company_pages job_links_selector is required in config")
        return errors

    def _list_url(self, source: JobSourceConfig) -> str:
        """Return the listing URL for the source."""
        return str(source.config.get("list_url") or source.base_url)

    def _health_url(self, source: JobSourceConfig) -> str:
        """Health checks hit the jobs listing page."""
        return self._list_url(source)

    def _initial_cursor(self, source: JobSourceConfig) -> dict[str, Any]:
        """Start crawling at the first listing page."""
        return {"url": self._list_url(source), "page": 1}

    def _fetch_page(self, source: JobSourceConfig, cursor: dict[str, Any]) -> PageResult:
        """Fetch a listing page and optional job detail pages."""
        page_url = cursor["url"]
        page_number = int(cursor.get("page", 1))
        html = self._http.get_text(page_url)
        soup = parse_html(html)

        selector = str(source.config.get("job_links_selector"))
        anchors = css_select(soup, selector)
        scrape_details = bool(source.config.get("scrape_details", True))
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for anchor in anchors:
            href = extract_href(anchor, page_url)
            if not href or href in seen:
                continue
            seen.add(href)
            if scrape_details:
                item = self._scrape_detail(href, source)
            else:
                item = {
                    "title": extract_text(anchor),
                    "url": href,
                    "description": None,
                }
            if item is not None:
                items.append(item)

        next_url = self._find_next_page(soup, page_url, source)
        max_pages = int(source.config.get("max_pages", 1) or 1)
        next_cursor = (
            {"url": next_url, "page": page_number + 1}
            if next_url and page_number < max_pages
            else None
        )
        return PageResult(items=items, next_cursor=next_cursor)

    def _find_next_page(self, soup: Any, page_url: str, source: JobSourceConfig) -> str | None:  # noqa: ANN401
        """Locate the next listing page URL via the configured selector."""
        selector = source.config.get("next_page_selector")
        if not selector:
            return None
        link = css_select_first(soup, str(selector))
        return extract_href(link, page_url)

    def _scrape_detail(self, url: str, source: JobSourceConfig) -> dict[str, Any] | None:
        """Fetch a job detail page and extract title/description."""
        self._rate_limiter.wait()
        html = self._http.get_text(url)
        soup = parse_html(html)

        title_element = css_select_first(soup, str(source.config.get("title_selector")))
        title = extract_text(title_element)

        description_element = css_select_first(soup, str(source.config.get("description_selector")))
        description = extract_text(description_element)
        if not description:
            description = self._json_ld_description(soup)

        if not title:
            title = self._json_ld_title(soup)

        external_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return {
            "external_id": external_id,
            "title": title,
            "url": url,
            "description": description,
            "raw_html_size": len(html),
        }

    def _json_ld_title(self, soup: Any) -> str | None:  # noqa: ANN401
        """Extract a job title from JSON-LD structured data."""
        for block in extract_json_ld(soup):
            if block.get("@type") in ("JobPosting", ["JobPosting"]):
                title = block.get("title")
                if title:
                    return clean_text(str(title))
        return None

    def _json_ld_description(self, soup: Any) -> str | None:  # noqa: ANN401
        """Extract a description from JSON-LD structured data."""
        for block in extract_json_ld(soup):
            if block.get("@type") in ("JobPosting", ["JobPosting"]):
                description = block.get("description")
                if description:
                    return clean_text(str(description))
        return None

    def normalize(self, raw: dict[str, Any], source: JobSourceConfig) -> DiscoveredJob | None:
        """Convert a scraped job record into a discovered job."""
        title = clean_text(raw.get("title"))
        url = clean_text(raw.get("url"))
        if not title or not url:
            return None
        company = source.config.get("company") or self._company_name(source)

        return DiscoveredJob(
            external_id=clean_text(raw.get("external_id")),
            url=url,
            title=title,
            company=company,
            location=None,
            description=clean_text(raw.get("description")),
            department=None,
            employment_type=None,
            remote_status=None,
            requirements=None,
            raw_payload=raw,
            discovered_at=utc_now(),
            posted_at=None,
        )

    def _company_name(self, source: JobSourceConfig) -> str | None:
        """Infer a company name from the list URL host."""
        from urllib.parse import urlparse

        host = urlparse(self._list_url(source)).hostname or ""
        return host.split(".")[0] or None
