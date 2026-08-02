from __future__ import annotations

from dataclasses import dataclass

import pytest
import requests
from app.config.providers_config import ProviderConfig
from app.config.settings import Settings
from app.domain.jobs.errors import SourceFetchError
from app.infrastructure.http.client import HttpClient


@dataclass
class _FakeResponse:
    """Minimal requests.Response test double."""

    status_code: int
    body: str | dict = ""

    def json(self) -> dict | str:
        """Return the JSON body."""
        return self.body if isinstance(self.body, (dict, list)) else {}

    @property
    def text(self) -> str:
        """Return the text body."""
        return str(self.body)

    def raise_for_status(self) -> None:
        """Raise if the status code indicates an error."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class _FakeSession:
    """Session test double that records calls and returns queued responses."""

    def __init__(self, responses: list[_FakeResponse]) -> None:
        """Initialize with a queue of responses."""
        self._responses = responses
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        """Return the next queued response and record the call."""
        self.calls.append((method, url, kwargs))
        return self._responses.pop(0)


def _provider(retry_attempts: int = 3, timeout: int = 10) -> ProviderConfig:
    """Build a provider config for HTTP tests."""
    return ProviderConfig(
        name="test_provider",
        enabled=True,
        timeout_seconds=timeout,
        retry_attempts=retry_attempts,
        min_interval_seconds=0.0,
        rate_limit_per_minute=60,
        base_headers={"X-Provider": "test"},
    )


def test_http_client_sends_expected_headers_and_timeout() -> None:
    """The client should merge base headers, User-Agent, and per-call headers."""
    fake = _FakeSession([_FakeResponse(200, {"ok": True})])
    client = HttpClient(Settings(), config=_provider())
    client._session = fake

    client.get("https://example.com", headers={"X-Custom": "yes"})

    method, url, kwargs = fake.calls[0]
    assert method == "get"
    assert url == "https://example.com"
    assert kwargs["headers"]["User-Agent"] == Settings().discovery_user_agent
    assert kwargs["headers"]["X-Provider"] == "test"
    assert kwargs["headers"]["X-Custom"] == "yes"
    assert kwargs["timeout"] == 10


def test_http_client_get_json_decodes_body() -> None:
    """get_json should return the decoded JSON payload."""
    fake = _FakeSession([_FakeResponse(200, {"count": 3})])
    client = HttpClient(Settings(), config=_provider())
    client._session = fake

    data = client.get_json("https://example.com/api")

    assert data == {"count": 3}


def test_http_client_retries_retryable_status() -> None:
    """A 503 response should be retried before succeeding."""
    fake = _FakeSession([_FakeResponse(503), _FakeResponse(200, {"ok": True})])
    client = HttpClient(Settings(), config=_provider(retry_attempts=3))
    client._session = fake

    response = client.get("https://example.com")

    assert response.status_code == 200
    assert len(fake.calls) == 2


def test_http_client_retries_transient_exception() -> None:
    """A connection error should be retried before succeeding."""
    first = _FakeResponse(200)
    first_raise = _RaiseOnRequest(requests.ConnectionError("boom"))

    class _SequenceSession(_FakeSession):
        def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
            self.calls.append((method, url, kwargs))
            response = self._responses.pop(0)
            if isinstance(response, _RaiseOnRequest):
                raise response.exc
            return response

    fake = _SequenceSession([first_raise, first])
    client = HttpClient(Settings(), config=_provider(retry_attempts=3))
    client._session = fake

    response = client.get("https://example.com")

    assert response.status_code == 200
    assert len(fake.calls) == 2


def test_http_client_raises_after_exhausting_retries() -> None:
    """Persistent failures should surface as SourceFetchError."""
    fake = _FakeSession([_FakeResponse(503), _FakeResponse(503), _FakeResponse(503)])
    client = HttpClient(Settings(), config=_provider(retry_attempts=2))
    client._session = fake

    with pytest.raises(SourceFetchError):
        client.get("https://example.com")


class _RaiseOnRequest:
    """Marker response wrapper that raises an exception when requested."""

    def __init__(self, exc: Exception) -> None:
        """Initialize with the exception to raise."""
        self.exc = exc
