"""Department-site fallback mapping for teacher -> department resolution."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlsplit

from bs4 import BeautifulSoup

from ..utils.html_cache import HtmlCache
from ..utils.http import HttpClient
from ..utils.text import none_if_empty


_STAFF_LINK_TOKENS = ("docent", "ricerc", "person", "people", "staff")
_TEACHER_PATH_RE = re.compile(r"/storage/teachers/([^/?#]+)/?", flags=re.IGNORECASE)


def crawl_department_teacher_map(
    departments: list[dict[str, object]],
    client: HttpClient,
    cache: HtmlCache | None = None,
    max_pages_per_department: int = 8,
) -> dict[str, str]:
    """Map teacher keys to department_id by crawling department public websites.

    Mapping keys:
    - `slug:<teacher_profile_slug>`
    - `email_local:<local_part>`
    """
    mapping: dict[str, str] = {}
    for department in departments:
        department_id = department.get("department_id")
        if not isinstance(department_id, str) or not department_id:
            continue

        base_urls = _department_seed_urls(department)
        for base_url in base_urls:
            for key in _crawl_department_keys(
                base_url=base_url,
                client=client,
                cache=cache,
                max_pages=max_pages_per_department,
            ):
                mapping.setdefault(key, department_id)
    return mapping


def _crawl_department_keys(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None,
    max_pages: int,
) -> set[str]:
    to_visit: list[str] = [base_url]
    visited: set[str] = set()
    keys: set[str] = set()
    base_host = urlparse(base_url).netloc

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html = _try_fetch_html(url=url, client=client, cache=cache)
        if html is None:
            continue

        page_keys, candidate_links = _extract_keys_and_candidate_links(
            html=html,
            page_url=url,
            allowed_host=base_host,
        )
        keys.update(page_keys)

        for candidate in sorted(candidate_links):
            if candidate not in visited and candidate not in to_visit:
                to_visit.append(candidate)

    return keys


def _department_seed_urls(department: dict[str, object]) -> list[str]:
    seeds: set[str] = set()
    for field in ("website_url", "source_url"):
        value = department.get(field)
        if not isinstance(value, str):
            continue
        normalized = _normalize_seed_url(value)
        if normalized:
            seeds.add(normalized)
    return sorted(seeds)


def _normalize_seed_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc.endswith(".unical.it"):
        return None
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path if parsed.path else "/"
    if not path.endswith("/"):
        path = f"{path}/"
    return f"{base}{path}"


def _extract_keys_and_candidate_links(
    html: str,
    page_url: str,
    allowed_host: str,
) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(html, "html.parser")
    keys: set[str] = set()
    candidate_links: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        if href.startswith("mailto:"):
            local_part = _email_local_part(href.replace("mailto:", "", 1))
            if local_part:
                keys.add(f"email_local:{local_part}")
            continue

        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        lower_text = anchor.get_text(" ", strip=True).casefold()
        lower_url = absolute.casefold()

        slug = _teacher_slug_from_url(absolute)
        if slug:
            keys.add(f"slug:{slug}")

        if parsed.netloc != allowed_host:
            continue
        if any(token in lower_text for token in _STAFF_LINK_TOKENS) or any(
            token in lower_url for token in _STAFF_LINK_TOKENS
        ):
            candidate_links.add(_strip_query_fragment(absolute))

    return keys, candidate_links


def _teacher_slug_from_url(url: str) -> str | None:
    match = _TEACHER_PATH_RE.search(url)
    if not match:
        return None
    slug = none_if_empty(match.group(1).strip().casefold())
    return slug


def _email_local_part(email: str) -> str | None:
    if "@" not in email:
        return None
    local = none_if_empty(email.split("@", maxsplit=1)[0].strip().casefold())
    return local


def _strip_query_fragment(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _try_fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str | None:
    try:
        if cache is None:
            return client.get_text(url)
        return cache.get_or_fetch(url, client.get_text)
    except Exception:
        return None
