"""HTTP helpers with explicit user-agent and rate limiting."""

from __future__ import annotations

import time

import httpx


DEFAULT_USER_AGENT = (
    "UNICAL-Campus-App-Scraper/0.1 "
    "(+https://github.com/unical-campus-app/unical-campus-app)"
)


class HttpClient:
    """Small HTTP client wrapper for respectful scraping defaults."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 30.0,
        rate_limit_seconds: float = 0.5,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )
        self._rate_limit_seconds = max(rate_limit_seconds, 0.0)
        self._last_request_at: float | None = None

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is not None and self._rate_limit_seconds > 0:
            elapsed = time.monotonic() - self._last_request_at
            wait_for = self._rate_limit_seconds - elapsed
            if wait_for > 0:
                time.sleep(wait_for)

    def get_text(self, url: str) -> str:
        """GET one URL while enforcing a simple fixed delay."""
        self._wait_for_rate_limit()
        response = self._client.get(url)
        response.raise_for_status()
        self._last_request_at = time.monotonic()
        return response.text

    def post_json(self, url: str, payload: dict[str, object]) -> str:
        """POST JSON while enforcing a simple fixed delay."""
        self._wait_for_rate_limit()
        response = self._client.post(url, json=payload)
        response.raise_for_status()
        self._last_request_at = time.monotonic()
        return response.text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
