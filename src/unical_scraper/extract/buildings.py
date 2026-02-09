"""Buildings extraction from official UNICAL campus map sources."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from ..utils.html_cache import HtmlCache
from ..utils.http import HttpClient
from ..utils.text import collapse_whitespace, none_if_empty


KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


@dataclass(frozen=True)
class RawBuilding:
    """Raw building record extracted before normalization."""

    name: str
    source_url: str
    lat: float
    lng: float
    description: str | None = None


def crawl_buildings(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None = None,
) -> list[RawBuilding]:
    """Crawl building-like map markers from the official UNICAL map page."""
    map_html = _fetch_html(base_url, client, cache)
    kml_url = _extract_kml_url(map_html=map_html, base_url=base_url)
    if not kml_url:
        return []

    kml_text = _fetch_html(kml_url, client, cache)
    return _parse_buildings_kml(kml_text=kml_text, source_url=base_url)


def _fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str:
    if cache is None:
        return client.get_text(url)
    return cache.get_or_fetch(url, client.get_text)


def _extract_kml_url(map_html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(map_html, "html.parser")

    candidates: list[str] = []
    for iframe in soup.select("iframe[src]"):
        candidates.append(iframe.get("src", ""))
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if "google.com/maps/d" in href:
            candidates.append(href)

    for candidate in candidates:
        absolute = _to_absolute_url(base_url=base_url, href=html.unescape(candidate))
        mid = _extract_mid_from_google_maps_url(absolute)
        if not mid:
            continue
        return f"https://www.google.com/maps/d/kml?mid={mid}&forcekml=1"

    return None


def _to_absolute_url(base_url: str, href: str) -> str:
    if href.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{href}"
    return urljoin(base_url, href)


def _extract_mid_from_google_maps_url(url: str) -> str | None:
    parsed = urlparse(url)
    if "google.com" not in parsed.netloc:
        return None

    params = parse_qs(parsed.query)
    mid_values = params.get("mid", [])
    for value in mid_values:
        if value:
            return value
    return None


def _parse_buildings_kml(kml_text: str, source_url: str) -> list[RawBuilding]:
    root = ET.fromstring(kml_text.lstrip())
    buildings: list[RawBuilding] = []

    for folder in root.findall(".//kml:Folder", KML_NS):
        folder_name = _normalize_text(folder.findtext("kml:name", default="", namespaces=KML_NS))
        if not folder_name:
            continue

        for placemark in folder.findall("kml:Placemark", KML_NS):
            raw_name = _normalize_text(placemark.findtext("kml:name", default="", namespaces=KML_NS))
            if not raw_name:
                continue
            if not _is_building_candidate(name=raw_name):
                continue

            coords = _extract_first_coordinates(placemark)
            if not coords:
                continue
            lng, lat = coords

            description = _normalize_text(
                _strip_html(
                    placemark.findtext("kml:description", default="", namespaces=KML_NS)
                )
            )

            buildings.append(
                RawBuilding(
                    name=raw_name,
                    source_url=source_url,
                    lat=lat,
                    lng=lng,
                    description=description,
                )
            )

    unique_by_name: dict[str, RawBuilding] = {}
    for building in buildings:
        key = building.name.casefold()
        unique_by_name.setdefault(key, building)

    return sorted(unique_by_name.values(), key=lambda item: item.name.casefold())


def _extract_first_coordinates(placemark: ET.Element) -> tuple[float, float] | None:
    coordinates_text = placemark.findtext(".//kml:coordinates", default="", namespaces=KML_NS)
    if not coordinates_text:
        return None

    first_coord = coordinates_text.strip().split()[0]
    parts = [part.strip() for part in first_coord.split(",")]
    if len(parts) < 2:
        return None

    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except ValueError:
        return None
    return lng, lat


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\xa0", " ")
    normalized = collapse_whitespace(normalized)
    return none_if_empty(normalized)


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    no_tags = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(no_tags)


def _is_building_candidate(name: str) -> bool:
    lowered = name.casefold()

    excluded_tokens = [
        "fontanella",
        "parcheggio",
        "pensiline",
        "terminal bus",
        "wifi",
        "copertura",
        "strada",
        "casetta dell'acqua",
        "bar ",
        "banca ",
        "campo ",
    ]
    if any(token in lowered for token in excluded_tokens):
        return False

    if lowered.startswith(("cubo ", "cubi ")):
        return True

    include_tokens = [
        "aula magna",
        "teatro",
        "biblioteca",
        "mensa",
        "residenza",
        "quartiere",
        "maisonnettes",
        "palestra",
        "rettorato",
        "centro",
        "museo",
        "cla",
    ]
    return any(token in lowered for token in include_tokens)
