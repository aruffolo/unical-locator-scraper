from __future__ import annotations

from unical_scraper.utils.html_cache import HtmlCache


def test_request_cache_reuses_identical_post_payloads(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    calls = {"count": 0}

    def fetcher() -> str:
        calls["count"] += 1
        return "payload-a"

    first = cache.get_or_fetch_request(
        method="POST",
        url="https://planner.example/api/Aule/getAulePerCalendarioPubblico",
        payload={"clienteId": "client-1", "linkCalendarioId": "aaaaaaaaaaaaaaaaaaaaaaaa"},
        fetcher=fetcher,
    )
    second = cache.get_or_fetch_request(
        method="POST",
        url="https://planner.example/api/Aule/getAulePerCalendarioPubblico",
        payload={"linkCalendarioId": "aaaaaaaaaaaaaaaaaaaaaaaa", "clienteId": "client-1"},
        fetcher=fetcher,
    )

    assert first == "payload-a"
    assert second == "payload-a"
    assert calls["count"] == 1


def test_request_cache_separates_post_payloads(tmp_path) -> None:
    cache = HtmlCache(tmp_path / "cache")
    calls = {"count": 0}

    def fetcher_a() -> str:
        calls["count"] += 1
        return "payload-a"

    def fetcher_b() -> str:
        calls["count"] += 1
        return "payload-b"

    first = cache.get_or_fetch_request(
        method="POST",
        url="https://planner.example/api/Aule/getAulePerCalendarioPubblico",
        payload={"clienteId": "client-1", "linkCalendarioId": "aaaaaaaaaaaaaaaaaaaaaaaa"},
        fetcher=fetcher_a,
    )
    second = cache.get_or_fetch_request(
        method="POST",
        url="https://planner.example/api/Aule/getAulePerCalendarioPubblico",
        payload={"clienteId": "client-1", "linkCalendarioId": "bbbbbbbbbbbbbbbbbbbbbbbb"},
        fetcher=fetcher_b,
    )

    assert first == "payload-a"
    assert second == "payload-b"
    assert calls["count"] == 2
