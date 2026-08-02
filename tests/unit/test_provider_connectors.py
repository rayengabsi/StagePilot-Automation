from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config.settings import Settings
from app.domain.jobs.entities import JobSourceConfig
from app.domain.jobs.enums import JobSourceType
from app.infrastructure.job_sources.ashby_connector import AshbyConnector
from app.infrastructure.job_sources.company_pages_connector import CompanyPagesConnector
from app.infrastructure.job_sources.greenhouse_connector import GreenhouseConnector
from app.infrastructure.job_sources.lever_connector import LeverConnector
from app.infrastructure.job_sources.rate_limiter import RateLimiter
from app.infrastructure.job_sources.remote_ok_connector import RemoteOkConnector
from app.infrastructure.job_sources.smart_recruiters_connector import SmartRecruitersConnector
from app.infrastructure.job_sources.teamtailor_connector import TeamtailorConnector
from app.infrastructure.job_sources.welcome_to_the_jungle_connector import (
    WelcomeToTheJungleConnector,
)
from app.infrastructure.job_sources.wellfound_connector import WellfoundConnector


class _FakeHttp:
    """HTTP client test double driven by per-verb handler callables."""

    def __init__(self) -> None:
        """Initialize with default handlers that fail loudly."""
        self.get_json_handler: Callable[..., Any] | None = None
        self.post_json_handler: Callable[..., Any] | None = None
        self.get_text_handler: Callable[..., str] | None = None
        self.calls: list[str] = []

    def get_json(self, url: str, *, headers=None, params=None) -> Any:  # noqa: ANN001, ANN401
        """Delegate to the configured get_json handler."""
        self.calls.append(f"get_json {url}")
        assert self.get_json_handler is not None
        return self.get_json_handler(url=url, headers=headers, params=params)

    def post_json(self, url: str, *, headers=None, json=None) -> Any:  # noqa: ANN001, ANN401
        """Delegate to the configured post_json handler."""
        self.calls.append(f"post_json {url}")
        assert self.post_json_handler is not None
        return self.post_json_handler(url=url, headers=headers, json=json)

    def get_text(self, url: str, *, headers=None, params=None) -> str:  # noqa: ANN001
        """Delegate to the configured get_text handler."""
        self.calls.append(f"get_text {url}")
        assert self.get_text_handler is not None
        return self.get_text_handler(url=url, headers=headers, params=params)


def _connector(connector_cls: type, fake: _FakeHttp) -> object:
    """Build a connector with a fake HTTP client and no throttling."""
    return connector_cls(Settings(), http_client=fake, rate_limiter=RateLimiter(0.0))


def _source(
    source_type: JobSourceType,
    base_url: str = "https://example.com",
    config: dict[str, Any] | None = None,
) -> JobSourceConfig:
    """Build a standard source config."""
    return JobSourceConfig(
        id=1,
        name="Test Source",
        type=source_type,
        base_url=base_url,
        config=config or {},
    )


class TestGreenhouseConnector:
    def test_fetch_normalizes_greenhouse_job(self) -> None:
        """Greenhouse jobs should normalize with metadata fields."""
        fake = _FakeHttp()
        payload = {
            "jobs": [
                {
                    "id": "123",
                    "title": "Backend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                    "location": {"name": "Paris, France"},
                    "departments": [{"name": "Engineering"}],
                    "employment_type": {"name": "Full-time"},
                    "remote": True,
                    "content": "<p>Build APIs</p>",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
            "meta": {"page": 1, "total": 1, "per_page": 10},
        }
        fake.get_json_handler = lambda **_kwargs: payload

        jobs = _connector(GreenhouseConnector, fake).fetch(
            _source(
                JobSourceType.GREENHOUSE,
                base_url="https://boards.greenhouse.io/acme",
                config={"company": "Acme"},
            )
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert job.external_id == "123"
        assert job.title == "Backend Engineer"
        assert job.company == "Acme"
        assert job.location == "Paris, France"
        assert job.department == "Engineering"
        assert job.employment_type == "Full-time"
        assert job.remote_status == "remote"
        assert job.posted_at is not None

    def test_fetch_paginates_with_meta(self) -> None:
        """Greenhouse pagination should advance while more pages remain."""
        fake = _FakeHttp()
        page_1 = {
            "jobs": [{"id": "1", "title": "A", "absolute_url": "https://x/1"}],
            "meta": {"page": 1, "total": 2, "per_page": 1},
        }
        page_2 = {
            "jobs": [{"id": "2", "title": "B", "absolute_url": "https://x/2"}],
            "meta": {"page": 2, "total": 2, "per_page": 1},
        }
        pages = iter([page_1, page_2])
        fake.get_json_handler = lambda **_kwargs: next(pages)

        jobs = _connector(GreenhouseConnector, fake).fetch(
            _source(JobSourceType.GREENHOUSE, config={"token": "acme"})
        )

        assert len(jobs) == 2


class TestLeverConnector:
    def test_fetch_parses_list_response(self) -> None:
        """Lever returns a flat list of postings."""
        fake = _FakeHttp()
        payload = [
            {
                "id": "abc",
                "text": "Frontend Engineer",
                "hostedUrl": "https://jobs.lever.co/acme/abc",
                "categories": {
                    "location": "Remote",
                    "team": "Engineering",
                    "commitment": "Full-time",
                },
                "descriptionPlain": "Build UI with React. Remote friendly.",
                "lists": [{"title": "Requirements", "content": "3+ years React"}],
                "createdAt": 1735689600000,
            }
        ]
        fake.get_json_handler = lambda **_kwargs: payload

        jobs = _connector(LeverConnector, fake).fetch(
            _source(JobSourceType.LEVER, config={"company": "acme"})
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert job.department == "Engineering"
        assert job.remote_status == "remote"
        assert job.requirements == "3+ years React"


class TestAshbyConnector:
    def test_fetch_posts_board_identifier(self) -> None:
        """Ashby should POST the board identifier and follow cursors."""
        fake = _FakeHttp()
        page_1 = {
            "jobs": [{"id": "1", "title": "A", "jobUrl": "https://x/1"}],
            "hasMore": True,
            "nextCursor": "cur",
        }
        page_2 = {
            "jobs": [{"id": "2", "title": "B", "jobUrl": "https://x/2"}],
            "hasMore": False,
            "nextCursor": None,
        }
        pages = iter([page_1, page_2])

        def _post(url: str, *, json: dict[str, Any] | None, **_kwargs: Any) -> dict:  # noqa: ANN401
            assert json is not None
            assert json["boardIdentifier"] == "acme"
            return next(pages)

        fake.post_json_handler = _post

        jobs = _connector(AshbyConnector, fake).fetch(
            _source(JobSourceType.ASHBY, config={"board": "acme"})
        )

        assert len(jobs) == 2


class TestSmartRecruitersConnector:
    def test_fetch_parses_paged_content(self) -> None:
        """SmartRecruiters should paginate by offset."""
        fake = _FakeHttp()
        page_1 = {
            "content": [
                {
                    "id": "r1",
                    "name": "Data Scientist",
                    "ref": "https://jobs.smartrecruiters.com/acme/r1",
                    "location": {"city": "Lyon", "country": "France"},
                    "department": {"label": "Data"},
                    "releasedDate": "2026-02-01T00:00:00Z",
                    "jobAd": {
                        "sections": [{"title": "description", "jobDescription": "Analyze data"}]
                    },
                }
            ],
            "totalFound": 1,
        }
        fake.get_json_handler = lambda **_kwargs: page_1

        jobs = _connector(SmartRecruitersConnector, fake).fetch(
            _source(JobSourceType.SMART_RECRUITERS, config={"company": "acme"})
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert job.location == "Lyon, France"
        assert job.department == "Data"


class TestTeamtailorConnector:
    def test_fetch_resolves_relationships(self) -> None:
        """Teamtailor should resolve department/location from included data."""
        fake = _FakeHttp()
        payload = {
            "data": [
                {
                    "id": "tt-1",
                    "attributes": {
                        "title": "DevOps Engineer",
                        "url": "https://careers.teamtailor.com/jobs/tt-1",
                        "body": "Run infrastructure",
                        "remote": True,
                    },
                    "relationships": {
                        "department": {"data": {"id": "d1", "type": "departments"}},
                        "location": {"data": {"id": "l1", "type": "locations"}},
                    },
                }
            ],
            "included": [
                {"id": "d1", "type": "departments", "attributes": {"name": "Platform"}},
                {
                    "id": "l1",
                    "type": "locations",
                    "attributes": {"city": "Berlin", "country": "Germany"},
                },
            ],
            "meta": {"pagination": {"current-page": 1, "last-page": 1}},
        }
        fake.get_json_handler = lambda **_kwargs: payload

        jobs = _connector(TeamtailorConnector, fake).fetch(
            _source(JobSourceType.TEAMTAILOR, config={"api_key": "secret"})
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert job.department == "Platform"
        assert job.location == "Berlin, Germany"
        assert job.remote_status == "remote"


class TestWelcomeToTheJungleConnector:
    def test_fetch_parses_wttj_job(self) -> None:
        """WelcomeKit jobs should normalize with location and contract type."""
        fake = _FakeHttp()
        payload = {
            "data": [
                {
                    "id": "slug-1",
                    "title": "Product Designer",
                    "url": "https://www.welcometothejungle.com/fr/companies/acme/jobs/slug-1",
                    "location": {"city": "Paris", "country": "France"},
                    "contract_type": {"text": "CDI"},
                    "description": "Design great products",
                    "published_at": "2026-03-01T00:00:00Z",
                }
            ]
        }
        fake.get_json_handler = lambda **_kwargs: payload

        jobs = _connector(WelcomeToTheJungleConnector, fake).fetch(
            _source(JobSourceType.WELCOME_TO_THE_JUNGLE, config={"slug": "acme"})
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert job.location == "Paris, France"
        assert job.employment_type == "CDI"


class TestRemoteOkConnector:
    def test_fetch_skips_metadata_first_element(self) -> None:
        """RemoteOK responses include a metadata head element to skip."""
        fake = _FakeHttp()
        payload = [
            {"location": "all"},
            {
                "id": 42,
                "position": "Python Developer",
                "company": "Remote Co",
                "url": "https://remoteok.com/remote-jobs/python-dev",
                "location": "Worldwide",
                "description": "<p>Build tools</p>",
                "tags": ["python", "aws"],
                "date": 1735689600,
            },
        ]
        fake.get_json_handler = lambda **_kwargs: payload

        jobs = _connector(RemoteOkConnector, fake).fetch(
            _source(JobSourceType.REMOTE_OK, base_url="https://remoteok.com")
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "Python Developer"
        assert job.remote_status == "remote"
        assert job.requirements == "python, aws"


class TestWellfoundConnector:
    def test_fetch_parses_wellfound_job(self) -> None:
        """Wellfound jobs should normalize with company and location."""
        fake = _FakeHttp()
        payload = {
            "jobs": [
                {
                    "id": 7,
                    "title": "Growth Marketer",
                    "company": {"name": "Startup Inc"},
                    "location": {"display_name": "Remote"},
                    "urls": {"apply_url": "https://wellfound.com/jobs/7"},
                    "description": "<p>Marketing</p>",
                    "created_at": "2026-04-01T00:00:00Z",
                }
            ],
            "total": 1,
        }
        fake.get_json_handler = lambda **_kwargs: payload

        jobs = _connector(WellfoundConnector, fake).fetch(
            _source(JobSourceType.WELLFOUND, config={"company": "Startup Inc"})
        )

        assert len(jobs) == 1
        job = jobs[0]
        assert job.company == "Startup Inc"
        assert job.location == "Remote"


class TestCompanyPagesConnector:
    def test_fetch_scrapes_list_only(self) -> None:
        """Company pages should extract job links from the listing page."""
        fake = _FakeHttp()
        html = (
            '<html><body><a class="job" href="/jobs/1">Job One</a>'
            '<a class="job" href="/jobs/2">Job Two</a></body></html>'
        )
        fake.get_text_handler = lambda **_kwargs: html
        source = _source(
            JobSourceType.COMPANY_PAGES,
            base_url="https://acme.com/careers",
            config={
                "company": "Acme",
                "job_links_selector": "a.job",
                "scrape_details": False,
            },
        )

        jobs = _connector(CompanyPagesConnector, fake).fetch(source)

        assert len(jobs) == 2
        assert jobs[0].title == "Job One"
        assert jobs[0].company == "Acme"
        assert jobs[0].url == "https://acme.com/jobs/1"

    def test_fetch_scrapes_details(self) -> None:
        """Company pages should extract details from each job page."""
        fake = _FakeHttp()
        list_html = '<a class="job" href="/jobs/1">Job One</a>'
        detail_html = (
            '<html><head><script type="application/ld+json">'
            '{"@type": "JobPosting", "title": "Job One", "description": "Do the work"}'
            "</script></head><body></body></html>"
        )

        def _get_text(url: str, **_kwargs: Any) -> str:  # noqa: ANN401
            if "/jobs/" in url:
                return detail_html
            return list_html

        fake.get_text_handler = _get_text
        source = _source(
            JobSourceType.COMPANY_PAGES,
            base_url="https://acme.com/careers",
            config={
                "company": "Acme",
                "job_links_selector": "a.job",
                "scrape_details": True,
            },
        )

        jobs = _connector(CompanyPagesConnector, fake).fetch(source)

        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == "Job One"
        assert job.description == "Do the work"
        assert job.external_id is not None


def test_connector_validate_reports_missing_config() -> None:
    """Each provider should flag missing required configuration."""
    fake = _FakeHttp()
    source = _source(JobSourceType.GREENHOUSE, config={})

    errors = _connector(GreenhouseConnector, fake).validate(source)

    assert any("token" in error for error in errors)
