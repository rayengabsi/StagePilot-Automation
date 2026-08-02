from __future__ import annotations

from app.infrastructure.html.parsing import (
    css_select,
    css_select_first,
    extract_attr,
    extract_href,
    extract_json_ld,
    extract_metadata,
    extract_text,
    parse_html,
    resolve_url,
    xpath_select,
)

_HTML = """
<html><head>
  <meta property="og:title" content="Job Title">
  <meta name="description" content="A description">
  <script type="application/ld+json">
  {"@type": "JobPosting", "title": "Engineer", "description": "<p>Build things</p>"}
  </script>
</head>
<body>
  <a class="job-link" href="/jobs/1">Job One</a>
  <a class="job-link" href="https://example.com/jobs/2">Job Two</a>
  <div class="job-card"><span>Title</span><p>Description text</p></div>
</body></html>
"""


def test_parse_html_and_css_select() -> None:
    """CSS selectors should find matching elements."""
    soup = parse_html(_HTML)
    links = css_select(soup, "a.job-link")

    assert len(links) == 2


def test_css_select_first_returns_none_when_missing() -> None:
    """Missing selector matches should return None."""
    soup = parse_html(_HTML)

    assert css_select_first(soup, "a.missing") is None
    assert css_select_first(soup, "a.job-link") is not None


def test_extract_metadata() -> None:
    """Meta tags should be extracted by name and property."""
    soup = parse_html(_HTML)
    metadata = extract_metadata(soup)

    assert metadata["og:title"] == "Job Title"
    assert metadata["description"] == "A description"


def test_extract_json_ld() -> None:
    """JSON-LD blocks should be parsed into dictionaries."""
    soup = parse_html(_HTML)
    blocks = extract_json_ld(soup)

    assert len(blocks) == 1
    assert blocks[0]["@type"] == "JobPosting"


def test_extract_text_and_attr() -> None:
    """Text and attribute helpers should normalize values."""
    soup = parse_html(_HTML)
    card = css_select_first(soup, "div.job-card")

    assert extract_text(card) == "Title Description text"
    assert extract_attr(css_select_first(soup, "a.job-link"), "class") == "job-link"


def test_extract_href_resolves_relative_urls() -> None:
    """Hrefs should be resolved against a base URL."""
    soup = parse_html(_HTML)
    first = css_select(soup, "a.job-link")[0]

    assert extract_href(first, "https://example.com/careers/") == "https://example.com/jobs/1"


def test_resolve_url() -> None:
    """resolve_url should join relative paths."""
    assert resolve_url("/jobs/1", "https://example.com") == "https://example.com/jobs/1"
    assert resolve_url(None, "https://example.com") is None


def test_xpath_select() -> None:
    """XPath expressions should return matching nodes."""
    results = xpath_select(_HTML, "//a[@class='job-link']")

    assert len(results) == 2
