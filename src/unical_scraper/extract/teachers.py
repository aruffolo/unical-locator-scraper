"""Teacher extraction helpers.

This module intentionally starts small and deterministic.
TODO: adapt selectors to real UNICAL HTML once source pages are frozen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from ..utils.html_cache import HtmlCache
from ..utils.http import HttpClient
from ..utils.text import collapse_whitespace, none_if_empty


@dataclass(frozen=True)
class RawTeacher:
    """Raw teacher record extracted from HTML before normalization."""

    full_name: str
    source_url: str
    email: str | None = None
    phone: str | None = None
    department_name: str | None = None
    website_url: str | None = None
    office_hours: str | None = None
    notes: str | None = None


def crawl_teachers(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None = None,
) -> list[RawTeacher]:
    """Crawl teachers from a UNICAL public page.

    Deterministic behavior:
    - links are deduplicated and sorted
    - output is sorted by normalized name
    """
    index_html = _fetch_html(base_url, client, cache)

    api_url = _extract_teachers_api_url(index_html=index_html, base_url=base_url)
    if api_url:
        teachers_from_api = _crawl_teachers_from_api(
            api_url=api_url,
            base_url=base_url,
            client=client,
            cache=cache,
        )
        if teachers_from_api:
            return teachers_from_api

    detail_urls = sorted(_parse_teacher_links(index_html, base_url))

    teachers: list[RawTeacher] = []
    if not detail_urls:
        # Fallback: page could already be a single profile.
        maybe_teacher = _parse_teacher_detail(index_html, base_url)
        if maybe_teacher:
            teachers.append(maybe_teacher)
        return teachers

    for url in detail_urls:
        html = _fetch_html(url, client, cache)
        teacher = _parse_teacher_detail(html, url)
        if teacher:
            teachers.append(teacher)

    unique_by_key: dict[tuple[str, str | None], RawTeacher] = {}
    for teacher in teachers:
        key = (teacher.full_name.casefold(), teacher.email)
        unique_by_key.setdefault(key, teacher)

    return sorted(unique_by_key.values(), key=lambda t: t.full_name.casefold())


def _fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str:
    if cache is None:
        return client.get_text(url)
    return cache.get_or_fetch(url, client.get_text)


def _parse_teacher_links(index_html: str, base_url: str) -> set[str]:
    """Extract candidate teacher profile links from an index/list page."""
    soup = BeautifulSoup(index_html, "html.parser")
    base_host = urlparse(base_url).netloc

    links: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if href.startswith("mailto:"):
            continue

        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc and parsed.netloc != base_host:
            continue

        lower_url = absolute.lower()
        lower_text = anchor.get_text(" ", strip=True).lower()
        if any(token in lower_url for token in ["/privacy", "/cookie", "/credits", "/sitemap"]):
            continue
        # TODO: replace heuristics with stable selectors when source HTML is finalized.
        if any(token in lower_url for token in ["docent", "teacher", "profile", "person"]):
            links.add(absolute)
        elif "docente" in lower_text or "prof." in lower_text:
            links.add(absolute)

    return links


def _parse_teacher_detail(detail_html: str, source_url: str) -> RawTeacher | None:
    """Parse one teacher profile page into a `RawTeacher` record."""
    soup = BeautifulSoup(detail_html, "html.parser")

    name_candidate = None
    for selector in ["h1", "h2", ".page-title", ".title"]:
        element = soup.select_one(selector)
        if element:
            name_candidate = collapse_whitespace(element.get_text(" ", strip=True))
            break

    if not name_candidate:
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        name_candidate = collapse_whitespace(title) if title else None

    if not name_candidate:
        return None

    email = None
    email_link = soup.select_one("a[href^='mailto:']")
    if email_link:
        email = none_if_empty(email_link.get("href", "").replace("mailto:", "").strip())

    website_url = None
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if href.startswith("http") and "mailto:" not in href:
            website_url = href
            break

    # TODO: use source-specific selectors to extract department and office hours accurately.
    return RawTeacher(
        full_name=name_candidate,
        source_url=source_url,
        email=email,
        website_url=website_url,
    )


def _extract_teachers_api_url(index_html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(index_html, "html.parser")
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if "/api/ricerca/teachers" not in href:
            continue
        if "format=json" not in href:
            continue
        return _to_absolute_url(base_url=base_url, href=href)
    return None


def _to_absolute_url(base_url: str, href: str) -> str:
    if href.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{href}"
    return urljoin(base_url, href)


def _crawl_teachers_from_api(
    api_url: str,
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None,
) -> list[RawTeacher]:
    teachers: list[RawTeacher] = []
    next_url: str | None = _with_page_size(api_url, page_size=200)
    visited: set[str] = set()

    while next_url and next_url not in visited:
        visited.add(next_url)
        payload = json.loads(_fetch_html(next_url, client, cache))
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            results = []

        for item in results:
            if not isinstance(item, dict):
                continue

            full_name = _extract_text(item.get("TeacherName"))
            if not full_name:
                continue

            email = _extract_first_email(item.get("Email"))
            department_name = _extract_text(item.get("TeacherDepartmentName"))
            website_url = _teacher_profile_url(base_url=base_url, email=email)
            source_url = website_url or api_url

            teachers.append(
                RawTeacher(
                    full_name=full_name,
                    source_url=source_url,
                    email=email,
                    department_name=department_name,
                    website_url=website_url,
                )
            )

        raw_next = payload.get("next") if isinstance(payload, dict) else None
        if isinstance(raw_next, str) and raw_next:
            next_url = _with_page_size(
                _to_absolute_url(base_url=api_url, href=raw_next),
                page_size=200,
            )
        else:
            next_url = None

    unique_by_key: dict[tuple[str, str | None], RawTeacher] = {}
    for teacher in teachers:
        key = (teacher.full_name.casefold(), teacher.email)
        unique_by_key.setdefault(key, teacher)

    return sorted(unique_by_key.values(), key=lambda teacher: teacher.full_name.casefold())


def _extract_first_email(value: object) -> str | None:
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                email = none_if_empty(entry.strip())
                if email:
                    return email
        return None
    if isinstance(value, str):
        return none_if_empty(value.strip())
    return None


def _teacher_profile_url(base_url: str, email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local_part = email.split("@", maxsplit=1)[0].strip()
    slug = none_if_empty(local_part)
    if not slug:
        return None
    return _to_absolute_url(base_url=base_url, href=f"/storage/teachers/{slug}/")


def _extract_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return none_if_empty(collapse_whitespace(value))


def _with_page_size(url: str, page_size: int) -> str:
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params["page_size"] = str(page_size)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
