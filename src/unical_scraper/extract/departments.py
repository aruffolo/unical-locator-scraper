"""Departments extraction helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..utils.html_cache import HtmlCache
from ..utils.http import HttpClient
from ..utils.text import collapse_whitespace, none_if_empty


@dataclass(frozen=True)
class RawDepartment:
    """Raw department record from source pages."""

    name: str
    source_url: str
    email: str | None = None
    phone: str | None = None
    website_url: str | None = None


def crawl_departments(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None = None,
) -> list[RawDepartment]:
    """Crawl department pages from a UNICAL public page."""
    index_html = _fetch_html(base_url, client, cache)

    api_url = _extract_departments_api_url(index_html=index_html, base_url=base_url)
    if api_url:
        departments_from_api = _crawl_departments_from_api(
            api_url=api_url,
            base_url=base_url,
            client=client,
            cache=cache,
        )
        if departments_from_api:
            return departments_from_api

    detail_urls = sorted(_parse_department_links(index_html, base_url))

    departments: list[RawDepartment] = []
    if not detail_urls:
        maybe_department = _parse_department_detail(index_html, base_url)
        if maybe_department:
            departments.append(maybe_department)
        return departments

    for url in detail_urls:
        html = _fetch_html(url, client, cache)
        department = _parse_department_detail(html, url)
        if department:
            departments.append(department)

    unique_by_key: dict[tuple[str, str | None], RawDepartment] = {}
    for department in departments:
        key = (department.name.casefold(), department.website_url)
        unique_by_key.setdefault(key, department)

    return sorted(unique_by_key.values(), key=lambda department: department.name.casefold())


def _fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str:
    if cache is None:
        return client.get_text(url)
    return cache.get_or_fetch(url, client.get_text)


def _parse_department_links(index_html: str, base_url: str) -> set[str]:
    """Extract candidate department detail links from a listing page."""
    soup = BeautifulSoup(index_html, "html.parser")
    base_host = urlparse(base_url).netloc

    links: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if href.startswith(("mailto:", "tel:")):
            continue

        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc and parsed.netloc != base_host:
            continue

        lower_url = absolute.lower()
        lower_text = anchor.get_text(" ", strip=True).lower()
        if "dipart" in lower_url or "dipartimento" in lower_text:
            links.add(absolute)

    links.discard(base_url)
    return links


def _parse_department_detail(detail_html: str, source_url: str) -> RawDepartment | None:
    """Parse one department detail page into a `RawDepartment` record."""
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

    phone = None
    phone_link = soup.select_one("a[href^='tel:']")
    if phone_link:
        phone = none_if_empty(phone_link.get("href", "").replace("tel:", "").strip())

    website_url = None
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()
        if not href or href.startswith(("mailto:", "tel:", "#")):
            continue
        if not href.startswith(("http://", "https://")):
            continue
        anchor_text = anchor.get_text(" ", strip=True).lower()
        if any(token in anchor_text for token in ("sito", "site", "website", "web")):
            website_url = href
            break
        if ".unical.it" in urlparse(href).netloc:
            website_url = href
            break

    return RawDepartment(
        name=name_candidate,
        source_url=source_url,
        email=email,
        phone=phone,
        website_url=website_url,
    )


def _extract_departments_api_url(index_html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(index_html, "html.parser")
    for text_node in soup.find_all(string=True):
        text = str(text_node)
        marker = "/api/ricerca/structures/"
        if marker not in text:
            continue
        start = text.find("http")
        if start == -1:
            start = text.find(marker)
        if start == -1:
            continue
        end = text.find('"', start)
        if end == -1:
            end = len(text)
        candidate = text[start:end].strip().strip("'")
        if marker not in candidate:
            continue
        return _to_absolute_url(base_url=base_url, href=candidate)
    return None


def _to_absolute_url(base_url: str, href: str) -> str:
    if href.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{href}"
    return urljoin(base_url, href)


def _crawl_departments_from_api(
    api_url: str,
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None,
) -> list[RawDepartment]:
    departments: list[RawDepartment] = []
    next_url: str | None = api_url
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

            name = _extract_text(item.get("StructureName"))
            if not name:
                continue

            website_url = _extract_text(item.get("StructureURL"))
            source_url = website_url or base_url

            departments.append(
                RawDepartment(
                    name=name,
                    source_url=source_url,
                    website_url=website_url,
                )
            )

        raw_next = payload.get("next") if isinstance(payload, dict) else None
        if isinstance(raw_next, str) and raw_next:
            next_url = _to_absolute_url(base_url=api_url, href=raw_next)
        else:
            next_url = None

    unique_by_key: dict[str, RawDepartment] = {}
    for department in departments:
        unique_by_key.setdefault(department.name.casefold(), department)

    return sorted(unique_by_key.values(), key=lambda department: department.name.casefold())


def _extract_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return none_if_empty(collapse_whitespace(value))
