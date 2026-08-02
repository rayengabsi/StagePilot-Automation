from __future__ import annotations

import logging
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from urllib3.util.retry import Retry

from app.config.providers_config import ProviderConfig
from app.config.settings import Settings
from app.domain.jobs.errors import SourceFetchError

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_EXCEPTIONS = (requests.Timeout, requests.ConnectionError, SourceFetchError)


class HttpClient:
    """Reusable HTTP client with retries, backoff, timeout, and pooling.

    Every provider connector shares one HttpClient instance, so request code
    is never duplicated and HTTP behavior is configured centrally.
    """

    def __init__(self, settings: Settings, config: ProviderConfig | None = None) -> None:
        """Initialize a session with connection pooling and retry policy."""
        self._settings = settings
        self._timeout = (
            config.timeout_seconds if config else settings.discovery_http_timeout_seconds
        )
        self._retry_attempts = (
            config.retry_attempts if config else settings.discovery_retry_attempts
        )
        self._base_headers = dict(config.base_headers) if config else {}
        self._session = requests.Session()

        http_adapter = requests.adapters.HTTPAdapter(
            max_retries=Retry(
                total=0,
                connect=0,
                read=0,
                backoff_factor=0,
                raise_on_status=False,
            ),
            pool_connections=10,
            pool_maxsize=10,
        )
        self._session.mount("http://", http_adapter)
        self._session.mount("https://", http_adapter)

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        """Perform a GET request with retries and structured logging."""
        logger.debug("http_get_started", extra={"url": url, "params": bool(params)})
        response = self._retrying_request(
            url, "get", headers=headers, params=params, timeout=timeout
        )
        logger.debug("http_get_succeeded", extra={"url": url, "status_code": response.status_code})
        return response

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        """Perform a POST request with retries and structured logging."""
        logger.debug("http_post_started", extra={"url": url})
        response = self._retrying_request(url, "post", json=json, headers=headers, timeout=timeout)
        logger.debug("http_post_succeeded", extra={"url": url, "status_code": response.status_code})
        return response

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:  # noqa: ANN401
        """Perform a GET request and decode the JSON body."""
        response = self.get(url, headers=headers, params=params)
        return response.json()

    def post_json(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:  # noqa: ANN401
        """Perform a POST request and decode the JSON body."""
        response = self.post(url, json=json, headers=headers)
        return response.json()

    def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Perform a GET request and return the raw text body."""
        return self.get(url, headers=headers, params=params).text

    def _retrying_request(
        self,
        url: str,
        method: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        retrying = retry(
            retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            stop=stop_after_attempt(self._retry_attempts),
            reraise=True,
        )(self._request_once)

        merged_headers = {**self._base_headers, "User-Agent": self._settings.discovery_user_agent}
        if headers:
            merged_headers.update(headers)
        try:
            return retrying(
                url,
                method=method,
                headers=merged_headers,
                params=params,
                json=json,
                timeout=timeout or self._timeout,
            )
        except requests.RequestException as exc:
            raise SourceFetchError(f"HTTP request failed for {url}: {exc}") from exc

    def _request_once(
        self,
        url: str,
        *,
        method: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        response = self._session.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json,
            timeout=timeout,
        )
        if response.status_code in _RETRYABLE_STATUS:
            raise SourceFetchError(f"Retryable HTTP status {response.status_code} from {url}")
        response.raise_for_status()
        return response
