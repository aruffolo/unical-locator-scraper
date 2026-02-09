"""Campus services extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..utils.html_cache import HtmlCache
from ..utils.http import HttpClient
from ..utils.text import collapse_whitespace, none_if_empty

@dataclass(frozen=True)
class RawService:
    """Raw service/office record from source pages."""

    name: str
    source_url: str
    service_type: str
    description: str | None = None
    email: str | None = None
    phone: str | None = None
    website_url: str | None = None
    opening_hours: str | None = None


def crawl_services(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None = None,
) -> list[RawService]:
    """Crawl service and secretary pages from UNICAL public pages."""
    index_html = _fetch_html(base_url, client, cache)
    first_level_urls = _parse_service_links(index_html, base_url)
    second_level_urls: set[str] = set()
    for url in sorted(first_level_urls):
        html = _fetch_html(url, client, cache)
        second_level_urls.update(_parse_service_links(html, url))
    detail_urls = sorted(first_level_urls | second_level_urls)

    services: list[RawService] = []
    if not detail_urls:
        services = _parse_service_cards(index_html, base_url)
        if services:
            return sorted(
                _dedupe_services(services),
                key=lambda service: (service.service_type, service.name.casefold()),
            )

        maybe_service = _parse_service_detail(index_html, base_url)
        if maybe_service:
            services.append(maybe_service)
        return services

    for url in detail_urls:
        html = _fetch_html(url, client, cache)
        service = _parse_service_detail(html, url)
        if service:
            services.append(service)

    return sorted(
        _dedupe_services(services),
        key=lambda service: (service.service_type, service.name.casefold()),
    )


def _dedupe_services(services: list[RawService]) -> list[RawService]:
    unique_by_key: dict[tuple[str, str, str | None], RawService] = {}
    for service in services:
        key = (service.service_type, service.name.casefold(), service.email)
        unique_by_key.setdefault(key, service)
    return list(unique_by_key.values())


def _fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str:
    if cache is None:
        return client.get_text(url)
    return cache.get_or_fetch(url, client.get_text)


def _parse_service_links(index_html: str, base_url: str) -> set[str]:
    """Extract candidate service links from a listing page."""
    soup = BeautifulSoup(index_html, "html.parser")
    base_host = urlparse(base_url).netloc

    links: set[str] = set()
    root = soup.select_one("main") or soup.select_one(".main-body") or soup
    for anchor in root.select("a[href]"):
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
        if "lang=" in lower_url or "javascript:" in lower_url:
            continue
        canonical_url = _canonical_service_url(absolute)
        if not canonical_url:
            continue
        lower_url = canonical_url.lower()

        lower_text = anchor.get_text(" ", strip=True).lower()
        if any(token in lower_text for token in ["home", "campus", "organizzazione"]):
            continue
        if not lower_text:
            continue
        if len(lower_text.split()) > 8 or len(lower_text) > 80:
            continue
        if any(
            token in lower_text
            for token in [
                "cookie",
                "rss",
                "faq",
                "calendario",
                "concerto",
                "evento",
                "avvisi",
                "seminario",
                "festival",
            ]
        ):
            continue
        links.add(canonical_url)

    links.discard(base_url)
    return links


def _parse_service_cards(index_html: str, source_url: str) -> list[RawService]:
    """Extract service cards from pages that already contain list details."""
    soup = BeautifulSoup(index_html, "html.parser")

    services: list[RawService] = []
    for container in soup.select("article, li, .card, .service, .servizio"):
        name_element = container.select_one("h1, h2, h3, h4, .title, strong")
        if not name_element:
            continue

        name = none_if_empty(collapse_whitespace(name_element.get_text(" ", strip=True)))
        if not name:
            continue

        description = None
        paragraph = container.select_one("p")
        if paragraph:
            description = none_if_empty(collapse_whitespace(paragraph.get_text(" ", strip=True)))

        email = None
        email_link = container.select_one("a[href^='mailto:']")
        if email_link:
            email = none_if_empty(email_link.get("href", "").replace("mailto:", "").strip())

        phone = None
        phone_link = container.select_one("a[href^='tel:']")
        if phone_link:
            phone = none_if_empty(phone_link.get("href", "").replace("tel:", "").strip())

        website_url = None
        for anchor in container.select("a[href]"):
            href = anchor.get("href", "").strip()
            if href.startswith(("http://", "https://")) and not href.startswith(("mailto:", "tel:")):
                website_url = href
                break

        services.append(
            RawService(
                name=name,
                source_url=source_url,
                service_type=_infer_service_type(name=name, context=description),
                description=description,
                email=email,
                phone=phone,
                website_url=website_url,
            )
        )

    return services


def _parse_service_detail(detail_html: str, source_url: str) -> RawService | None:
    """Parse one service detail page into a `RawService` record."""
    canonical_source_url = _canonical_service_url(source_url)
    if not canonical_source_url:
        return None

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
    if _is_noise_name(name_candidate):
        return None

    description = None
    paragraph = soup.select_one("main p, article p, p")
    if paragraph:
        description = none_if_empty(collapse_whitespace(paragraph.get_text(" ", strip=True)))

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
        website_url = href
        break

    opening_hours = None
    lower_page_text = soup.get_text(" ", strip=True).lower()
    if "orario" in lower_page_text:
        opening_hours = "Orari disponibili sulla pagina sorgente"

    return RawService(
        name=name_candidate,
        source_url=canonical_source_url,
        service_type=_infer_service_type(name=name_candidate, context=description),
        description=description,
        email=email,
        phone=phone,
        website_url=website_url,
        opening_hours=opening_hours,
    )


def _infer_service_type(name: str, context: str | None = None) -> str:
    text = f"{name} {context or ''}".casefold()
    if any(token in text for token in ["segreteria", "secretary"]):
        return "SECRETARY"
    if any(token in text for token in ["ufficio", "office"]):
        return "OFFICE"
    return "SERVICE"


def _is_noise_name(name: str) -> bool:
    lowered = name.casefold()
    if lowered in {
        "home",
        "campus",
        "i servizi del campus",
        "futuri studenti",
        "studenti iscritti",
        "laureati",
    }:
        return True
    return any(
        token in lowered
        for token in [
            "cookie",
            "faq",
            "calendario",
            "concerto",
            "evento",
            "avviso",
            "festival",
            "seminario",
            "feed",
            "click day",
        ]
    )


def _is_canonical_service_url(url: str) -> bool:
    return _canonical_service_url(url) is not None


def _canonical_service_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None

    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if not path_segments:
        return None

    lowered_segments = [segment.casefold() for segment in path_segments]
    lowered_path = "/".join(lowered_segments)

    blocked_tokens = [
        "contents",
        "news",
        "calendars",
        "events",
        "eventi",
        "archivio",
        "documentazione",
        "unicalfesta",
        "festival",
        "seminari",
        "modulistica",
        "viewer",
    ]
    if any(token in lowered_path for token in blocked_tokens):
        return None

    if lowered_segments[:2] == ["campus", "vivere-il-campus"]:
        if len(lowered_segments) < 3:
            return None
        return _join_path(parsed, lowered_segments[:3])
    if lowered_segments[:2] == ["campus", "servizi"]:
        if len(lowered_segments) < 3:
            return None
        return _join_path(parsed, lowered_segments[:3])
    if lowered_segments[:2] == ["didattica", "diritto-allo-studio"]:
        if len(lowered_segments) < 3:
            return None
        return _join_path(parsed, lowered_segments[:3])
    if lowered_segments[0] == "servizi-ict":
        if len(lowered_segments) == 1:
            return _join_path(parsed, lowered_segments[:1])
        return _join_path(parsed, lowered_segments[:2])
    if lowered_segments[:2] == ["ateneo", "servizi"]:
        if len(lowered_segments) < 3:
            return None
        return _join_path(parsed, lowered_segments[:3])

    if any(token in lowered_path for token in ["segreter", "servizi", "service", "ufficio"]):
        capped = lowered_segments[:3]
        return _join_path(parsed, capped)

    return None


def _join_path(parsed_url, segments: list[str]) -> str:
    canonical_path = "/" + "/".join(segments) + "/"
    return f"{parsed_url.scheme}://{parsed_url.netloc}{canonical_path}"
