"""Aula extraction from official UNICAL campus map sources."""

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
FLOOR_LABELS = [
    "Piano Terra",
    "Primo piano",
    "Secondo piano",
    "Terzo piano",
    "Quarto piano",
    "Quinto piano",
    "Sesto piano",
    "Settimo piano",
    "Altra collocazione",
]
FLOOR_PATTERN = re.compile(
    r"(" + "|".join(re.escape(label) for label in FLOOR_LABELS) + r")\s*(?:\([^)]*\))?\s*:\s*",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class RawAula:
    """Raw aula record extracted before normalization."""

    name: str
    source_url: str
    lat: float | None = None
    lng: float | None = None
    floor: str | None = None
    room: str | None = None
    short_code: str | None = None
    building_hint: str | None = None


def crawl_aulas(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None = None,
) -> list[RawAula]:
    """Crawl aula markers and aula mentions from the official UNICAL map."""
    map_html = _fetch_html(base_url, client, cache)
    kml_url = _extract_kml_url(map_html=map_html, base_url=base_url)
    if not kml_url:
        return []

    kml_text = _fetch_html(kml_url, client, cache)
    return _parse_aulas_kml(kml_text=kml_text, source_url=base_url)


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


def _parse_aulas_kml(kml_text: str, source_url: str) -> list[RawAula]:
    root = ET.fromstring(kml_text.lstrip())
    aulas: list[RawAula] = []

    for folder in root.findall(".//kml:Folder", KML_NS):
        folder_name = _normalize_text(folder.findtext("kml:name", default="", namespaces=KML_NS))
        for placemark in folder.findall("kml:Placemark", KML_NS):
            raw_name = _normalize_text(placemark.findtext("kml:name", default="", namespaces=KML_NS))
            if not raw_name:
                continue

            coords = _extract_first_coordinates(placemark)
            description = _normalize_text(
                _strip_html(placemark.findtext("kml:description", default="", namespaces=KML_NS))
            )
            building_hint = _extract_building_hint(f"{raw_name} {description or ''}")

            if _is_direct_aula_candidate(raw_name):
                canonical_name = _canonical_aula_name(raw_name)
                if canonical_name:
                    short_code = _extract_short_code(canonical_name)
                    room = _extract_room_label(canonical_name)
                    aulas.append(
                        RawAula(
                            name=canonical_name,
                            source_url=source_url,
                            lat=coords[1] if coords else None,
                            lng=coords[0] if coords else None,
                            room=room,
                            short_code=short_code,
                            building_hint=building_hint,
                        )
                    )

            if description and _may_contain_aulas(raw_name=raw_name, folder_name=folder_name):
                aulas.extend(
                    _extract_aulas_from_description(
                        description=description,
                        source_url=source_url,
                        lat=coords[1] if coords else None,
                        lng=coords[0] if coords else None,
                        building_hint=building_hint,
                    )
                )

    unique_by_key: dict[tuple[str, str | None, str | None], RawAula] = {}
    for aula in aulas:
        key = (
            collapse_whitespace(aula.name).casefold(),
            aula.floor.casefold() if aula.floor else None,
            aula.building_hint.casefold() if aula.building_hint else None,
        )
        unique_by_key.setdefault(key, aula)

    return sorted(
        unique_by_key.values(),
        key=lambda item: (
            item.name.casefold(),
            item.floor.casefold() if item.floor else "",
            item.building_hint.casefold() if item.building_hint else "",
        ),
    )


def _extract_aulas_from_description(
    description: str,
    source_url: str,
    lat: float | None,
    lng: float | None,
    building_hint: str | None,
) -> list[RawAula]:
    floor_matches = list(FLOOR_PATTERN.finditer(description))
    if not floor_matches:
        return []

    aulas: list[RawAula] = []
    for idx, match in enumerate(floor_matches):
        floor = _normalize_floor_label(match.group(1))
        segment_start = match.end()
        segment_end = floor_matches[idx + 1].start() if idx + 1 < len(floor_matches) else len(description)
        segment_text = collapse_whitespace(description[segment_start:segment_end])
        if not segment_text:
            continue

        for aula_name in _extract_aula_names_from_text(segment_text):
            canonical_name = _canonical_aula_name(aula_name)
            if not canonical_name:
                continue
            short_code = _extract_short_code(canonical_name)
            room = _extract_room_label(canonical_name)
            aulas.append(
                RawAula(
                    name=canonical_name,
                    source_url=source_url,
                    lat=lat,
                    lng=lng,
                    floor=floor,
                    room=room,
                    short_code=short_code,
                    building_hint=building_hint,
                )
            )

    return aulas


def _extract_aula_names_from_text(text: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"\bAula\s+[A-Za-z0-9][A-Za-z0-9'\- ]{0,40}", text, flags=re.IGNORECASE):
        value = collapse_whitespace(match.group(0))
        value = re.sub(r"\b(Link informativo|Evento)\b.*$", "", value, flags=re.IGNORECASE).strip()
        if value:
            candidates.append(value)
    return candidates


def _is_direct_aula_candidate(name: str) -> bool:
    lowered = name.casefold()
    if "aula " not in lowered:
        return False
    if any(token in lowered for token in ["convegno societa", "convegno società"]):
        return True
    return True


def _may_contain_aulas(raw_name: str, folder_name: str | None) -> bool:
    lowered_name = raw_name.casefold()
    if "cubo " in lowered_name or "aula " in lowered_name:
        return True
    lowered_folder = (folder_name or "").casefold()
    return "strutture" in lowered_folder


def _canonical_aula_name(name: str) -> str | None:
    cleaned = none_if_empty(collapse_whitespace(name.replace("\xa0", " ")))
    if not cleaned:
        return None

    if " - " in cleaned:
        head, tail = cleaned.split(" - ", maxsplit=1)
        lowered_tail = tail.casefold()
        if any(token in lowered_tail for token in ["convegno", "evento", "giorni"]):
            cleaned = head

    if not cleaned.casefold().startswith("aula "):
        return None

    return cleaned


def _extract_room_label(name: str) -> str | None:
    if not name.casefold().startswith("aula "):
        return None
    room = none_if_empty(collapse_whitespace(name[5:]))
    return room


def _extract_short_code(name: str) -> str | None:
    room = _extract_room_label(name)
    if not room:
        return None

    compact_room = room.replace(" ", "")
    if re.fullmatch(r"[A-Za-z]{1,4}\d{1,4}[A-Za-z]?", compact_room):
        return compact_room.upper()

    if re.fullmatch(r"(?:[A-Za-z]\s*){2,4}", room):
        letters = re.sub(r"\s+", "", room)
        return letters.upper()

    return None


def _extract_building_hint(text: str) -> str | None:
    text = collapse_whitespace(text)
    cubo_match = re.search(r"\bCubo\s+([0-9]{1,2}[A-Za-z])\b", text, flags=re.IGNORECASE)
    if cubo_match:
        return f"Cubo {cubo_match.group(1).upper()}"

    cubi_match = re.search(
        r"\bCubi\s+([0-9]{1,2}(?:-[0-9]{1,2})?[A-Za-z])\b",
        text,
        flags=re.IGNORECASE,
    )
    if cubi_match:
        return f"Cubi {cubi_match.group(1).upper()}"

    return None


def _normalize_floor_label(value: str) -> str:
    normalized = collapse_whitespace(value)
    lowered = normalized.casefold()
    for label in FLOOR_LABELS:
        if lowered == label.casefold():
            return label
    return normalized


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
