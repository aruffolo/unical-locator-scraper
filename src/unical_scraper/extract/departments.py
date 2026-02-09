"""Departments extraction helpers."""

from __future__ import annotations

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
