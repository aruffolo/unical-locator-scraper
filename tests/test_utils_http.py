from __future__ import annotations

import pytest

import httpx

from unical_scraper.utils.http import HttpClient


def test_http_client_retries_transport_errors_and_reports_diagnostics() -> None:
    url = "https://example.org/resource"
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("temporary failure", request=request)
        return httpx.Response(200, request=request, text="ok")

    transport = httpx.MockTransport(handler)
    with HttpClient(
        rate_limit_seconds=0.0,
        max_retries=2,
        retry_backoff_seconds=0.0,
        transport=transport,
    ) as client:
        body = client.get_text(url)
        summary = client.diagnostics_summary()

    assert body == "ok"
    assert call_count == 2
    assert summary["requests"] == 1
    assert summary["attempts"] == 2
    assert summary["retries"] == 1
    assert summary["final_failures"] == 0
    assert summary["retried_urls"] == [{"url": url, "retries": 1}]


def test_http_client_does_not_retry_non_retryable_http_status() -> None:
    url = "https://example.org/missing"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request, text="not found")

    transport = httpx.MockTransport(handler)
    with HttpClient(
        rate_limit_seconds=0.0,
        max_retries=3,
        retry_backoff_seconds=0.0,
        transport=transport,
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_text(url)
        summary = client.diagnostics_summary()

    assert summary["requests"] == 1
    assert summary["attempts"] == 1
    assert summary["retries"] == 0
    assert summary["final_failures"] == 1
    assert summary["retried_urls"] == []
