"""HTTP helpers with explicit user-agent and rate limiting."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

import httpx


DEFAULT_USER_AGENT = (
    "UNICAL-Campus-App-Scraper/0.1 "
    "(+https://github.com/unical-campus-app/unical-campus-app)"
)
DEFAULT_RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class HttpAttemptDiagnostic:
    method: str
    url: str
    attempt: int
    succeeded: bool
    status_code: int | None
    error_type: str | None
    retry_delay_seconds: float
    will_retry: bool


class HttpClient:
    """Small HTTP client wrapper for respectful scraping defaults."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 30.0,
        rate_limit_seconds: float = 0.5,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        retry_backoff_multiplier: float = 2.0,
        retryable_status_codes: set[int] | frozenset[int] = DEFAULT_RETRYABLE_STATUS_CODES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            transport=transport,
        )
        self._rate_limit_seconds = max(rate_limit_seconds, 0.0)
        self._max_retries = max(max_retries, 0)
        self._retry_backoff_seconds = max(retry_backoff_seconds, 0.0)
        self._retry_backoff_multiplier = max(retry_backoff_multiplier, 1.0)
        self._retryable_status_codes = set(retryable_status_codes)
        self._last_request_at: float | None = None
        self._request_count = 0
        self._retry_count = 0
        self._final_failure_count = 0
        self._diagnostics: list[HttpAttemptDiagnostic] = []

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is not None and self._rate_limit_seconds > 0:
            elapsed = time.monotonic() - self._last_request_at
            wait_for = self._rate_limit_seconds - elapsed
            if wait_for > 0:
                time.sleep(wait_for)

    def _backoff_delay_seconds(self, retry_number: int) -> float:
        return self._retry_backoff_seconds * (self._retry_backoff_multiplier ** max(retry_number - 1, 0))

    def _record_attempt(
        self,
        *,
        method: str,
        url: str,
        attempt: int,
        succeeded: bool,
        status_code: int | None,
        error_type: str | None,
        retry_delay_seconds: float,
        will_retry: bool = False,
    ) -> None:
        self._diagnostics.append(
            HttpAttemptDiagnostic(
                method=method,
                url=url,
                attempt=attempt,
                succeeded=succeeded,
                status_code=status_code,
                error_type=error_type,
                retry_delay_seconds=retry_delay_seconds,
                will_retry=will_retry,
            )
        )

    def _should_retry_http_status(self, status_code: int | None) -> bool:
        return status_code in self._retryable_status_codes if status_code is not None else False

    def _request(self, method: str, url: str, payload: dict[str, object] | None = None) -> httpx.Response:
        self._request_count += 1
        attempt = 1
        while True:
            self._wait_for_rate_limit()
            try:
                if method == "GET":
                    response = self._client.get(url)
                elif method == "POST":
                    response = self._client.post(url, json=payload)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                self._last_request_at = time.monotonic()
                self._record_attempt(
                    method=method,
                    url=url,
                    attempt=attempt,
                    succeeded=True,
                    status_code=response.status_code,
                    error_type=None,
                    retry_delay_seconds=0.0,
                    will_retry=False,
                )
                return response
            except httpx.HTTPStatusError as exc:
                self._last_request_at = time.monotonic()
                status_code = exc.response.status_code if exc.response is not None else None
                if attempt > self._max_retries or not self._should_retry_http_status(status_code):
                    self._final_failure_count += 1
                    self._record_attempt(
                        method=method,
                        url=url,
                        attempt=attempt,
                        succeeded=False,
                        status_code=status_code,
                        error_type=type(exc).__name__,
                        retry_delay_seconds=0.0,
                        will_retry=False,
                    )
                    raise

                retry_delay = self._backoff_delay_seconds(attempt)
                self._retry_count += 1
                self._record_attempt(
                    method=method,
                    url=url,
                    attempt=attempt,
                    succeeded=False,
                    status_code=status_code,
                    error_type=type(exc).__name__,
                    retry_delay_seconds=retry_delay,
                    will_retry=True,
                )
                if retry_delay > 0:
                    time.sleep(retry_delay)
                attempt += 1
            except httpx.TransportError as exc:
                self._last_request_at = time.monotonic()
                if attempt > self._max_retries:
                    self._final_failure_count += 1
                    self._record_attempt(
                        method=method,
                        url=url,
                        attempt=attempt,
                        succeeded=False,
                        status_code=None,
                        error_type=type(exc).__name__,
                        retry_delay_seconds=0.0,
                        will_retry=False,
                    )
                    raise

                retry_delay = self._backoff_delay_seconds(attempt)
                self._retry_count += 1
                self._record_attempt(
                    method=method,
                    url=url,
                    attempt=attempt,
                    succeeded=False,
                    status_code=None,
                    error_type=type(exc).__name__,
                    retry_delay_seconds=retry_delay,
                    will_retry=True,
                )
                if retry_delay > 0:
                    time.sleep(retry_delay)
                attempt += 1

    def get_text(self, url: str) -> str:
        """GET one URL while enforcing a simple fixed delay."""
        response = self._request("GET", url)
        return response.text

    def post_json(self, url: str, payload: dict[str, object]) -> str:
        """POST JSON while enforcing a simple fixed delay."""
        response = self._request("POST", url, payload)
        return response.text

    def diagnostics_summary(self) -> dict[str, object]:
        retried_url_counter = Counter(
            attempt.url for attempt in self._diagnostics if attempt.will_retry
        )
        retried_urls = [
            {"url": url, "retries": count}
            for url, count in sorted(retried_url_counter.items(), key=lambda item: (-item[1], item[0]))
        ]
        return {
            "requests": self._request_count,
            "attempts": len(self._diagnostics),
            "retries": self._retry_count,
            "final_failures": self._final_failure_count,
            "retried_urls": retried_urls,
        }

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
