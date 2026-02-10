"""Aula extraction from official UNICAL sources."""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .planner_link_ids import CURATED_PUBLIC_LINK_CALENDAR_IDS
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
FLOOR_WORD_TO_LABEL = {
    "terra": "Piano Terra",
    "primo": "Primo piano",
    "secondo": "Secondo piano",
    "terzo": "Terzo piano",
    "quarto": "Quarto piano",
    "quinto": "Quinto piano",
    "sesto": "Sesto piano",
    "settimo": "Settimo piano",
}
PLANNER_DEFAULT_BASE_URL = "https://unical.prod.up.cineca.it"
PLANNER_DEFAULT_CLIENT_ID = "5de6319d4414ab02f80b613a"
PLANNER_IMPEGNI_START = "2020-01-01"
PLANNER_IMPEGNI_END = "2030-12-31"
PLANNER_IMPEGNI_LIMIT = 20000
PLANNER_CALENDAR_DISCOVERY_SUBDOMAINS = (
    "dibest",
    "ctc",
    "dices",
    "desf",
    "dfssn",
    "fisica",
    "dinci",
    "diam",
    "dimes",
    "dimeg",
    "demacs",
    "discag",
    "dispes",
    "disu",
)
PLANNER_CALENDAR_DISCOVERY_PATHS = (
    "/",
    "/didattica/",
    "/didattica/frequentare-i-corsi/",
    "/didattica/iscriversi-studiare-laurearsi/frequentare-i-corsi/",
    "/didattica/iscriversi-studiare-laurearsi/bacheca-corsi-di-studio/",
    "/didattica/offerta-formativa/",
)
DEFAULT_CALENDAR_DISCOVERY_URLS = tuple(
    f"https://{subdomain}.unical.it{path}"
    for subdomain in PLANNER_CALENDAR_DISCOVERY_SUBDOMAINS
    for path in PLANNER_CALENDAR_DISCOVERY_PATHS
)
LINK_CALENDAR_ID_PATTERN = re.compile(r"linkCalendarioId=([0-9a-f]{24})", flags=re.IGNORECASE)
DEPARTMENT_SITE_SUBDOMAINS = (
    "dibest",
    "ctc",
    "dices",
    "desf",
    "dfssn",
    "fisica",
    "dinci",
    "diam",
    "dimes",
    "dimeg",
    "demacs",
    "discag",
    "dispes",
    "disu",
)
DEFAULT_DEPARTMENT_AULA_URLS = tuple(
    sorted(
        {
            *(f"https://{subdomain}.unical.it/dipartimento/organizzazione/strutture/" for subdomain in DEPARTMENT_SITE_SUBDOMAINS),
            "https://www2.dimes.unical.it/it/content/aule-dipartimento",
        }
    )
)
NOISE_AULA_TOKENS = (
    "nessun",
    "studio docente",
    "help desk",
    "sala consiglio",
    "calcio",
    "tennis",
    "padel",
    "palacus",
    "vibora",
    "chiodo",
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
    capacity: int | None = None


def crawl_aulas(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None = None,
    department_urls: tuple[str, ...] | list[str] | None = None,
    planner_base_url: str | None = PLANNER_DEFAULT_BASE_URL,
    planner_client_id: str | None = PLANNER_DEFAULT_CLIENT_ID,
    planner_calendar_discovery_urls: tuple[str, ...] | list[str] | None = None,
    planner_impegni_start: str | None = PLANNER_IMPEGNI_START,
    planner_impegni_end: str | None = PLANNER_IMPEGNI_END,
    planner_impegni_limit: int = PLANNER_IMPEGNI_LIMIT,
) -> list[RawAula]:
    """Crawl aulas from map, department pages and planner public endpoints."""
    aulas: list[RawAula] = []
    aulas.extend(_crawl_map_aulas(base_url=base_url, client=client, cache=cache))

    source_department_urls = tuple(department_urls or DEFAULT_DEPARTMENT_AULA_URLS)
    aulas.extend(_crawl_department_aulas(urls=source_department_urls, client=client, cache=cache))

    if planner_base_url:
        aulas.extend(
            _crawl_planner_aulas(
                planner_base_url=planner_base_url,
                client=client,
                cache=cache,
                planner_client_id=planner_client_id,
                calendar_discovery_urls=tuple(
                    planner_calendar_discovery_urls or DEFAULT_CALENDAR_DISCOVERY_URLS
                ),
                impegni_start=planner_impegni_start,
                impegni_end=planner_impegni_end,
                impegni_limit=planner_impegni_limit,
            )
        )

    return _dedupe_aulas(aulas)


def _crawl_map_aulas(base_url: str, client: HttpClient, cache: HtmlCache | None) -> list[RawAula]:
    try:
        map_html = _fetch_html(base_url, client, cache)
    except Exception:
        return []

    kml_url = _extract_kml_url(map_html=map_html, base_url=base_url)
    if not kml_url:
        return []

    try:
        kml_text = _fetch_html(kml_url, client, cache)
    except Exception:
        return []
    return _parse_aulas_kml(kml_text=kml_text, source_url=base_url)


def _crawl_department_aulas(
    urls: tuple[str, ...],
    client: HttpClient,
    cache: HtmlCache | None,
) -> list[RawAula]:
    aulas: list[RawAula] = []
    for url in sorted(set(urls)):
        html_text = _try_fetch_html(url=url, client=client, cache=cache)
        if not html_text:
            continue
        aulas.extend(_parse_department_aulas_html(html_text=html_text, source_url=url))
    return aulas


def _crawl_planner_aulas(
    planner_base_url: str,
    client: HttpClient,
    cache: HtmlCache | None,
    planner_client_id: str | None,
    calendar_discovery_urls: tuple[str, ...],
    impegni_start: str | None,
    impegni_end: str | None,
    impegni_limit: int,
) -> list[RawAula]:
    base = planner_base_url.rstrip("/")
    source_url = f"{base}/calendar/activities/"

    edifici_url = f"{base}/api/Edifici/getPerAutoCompletePublic?lookupFields=codice&limit=100"
    aula_list_url = f"{base}/api/Aule/getPerAutoCompletePublic?lookupFields=codice&limit=100"

    edifici_payload = _try_fetch_html(edifici_url, client=client, cache=cache)
    aule_payload = _try_fetch_html(aula_list_url, client=client, cache=cache)
    if not aule_payload:
        return []

    edifici_map: dict[str, str] = {}
    for item in _load_json_array(edifici_payload):
        item_id = item.get("id")
        descrizione = _normalize_text(str(item.get("descrizione", "")))
        if isinstance(item_id, str) and descrizione:
            edifici_map[item_id] = descrizione

    aulas: list[RawAula] = []
    for summary in _load_json_array(aule_payload):
        aula_id = summary.get("id")
        if not isinstance(aula_id, str):
            continue

        detail_url = f"{base}/api/Aule/getByIdPublic?id={aula_id}"
        detail_payload = _try_fetch_html(detail_url, client=client, cache=cache)
        detail = _load_json_object(detail_payload)
        if not detail:
            continue

        descrizione = _normalize_text(str(detail.get("descrizione") or summary.get("descrizione") or ""))
        codice = _normalize_text(str(detail.get("codice") or summary.get("codice") or ""))
        candidate_name = _canonical_planner_aula_name(descrizione or codice)
        if not candidate_name:
            continue

        edificio_id = detail.get("edificioId")
        building_hint = edifici_map.get(edificio_id) if isinstance(edificio_id, str) else None
        floor = _extract_floor_label(descrizione or "")

        short_code = _extract_short_code(candidate_name)
        room = _extract_room_label(candidate_name)
        aulas.append(
            RawAula(
                name=candidate_name,
                source_url=source_url,
                floor=floor,
                room=room,
                short_code=short_code,
                building_hint=building_hint,
            )
        )

    if planner_client_id:
        link_ids = set(CURATED_PUBLIC_LINK_CALENDAR_IDS)
        if calendar_discovery_urls:
            link_ids.update(
                _discover_calendar_link_ids(
                    urls=calendar_discovery_urls,
                    client=client,
                    cache=cache,
                )
            )
        if link_ids:
            aulas.extend(
                _crawl_planner_aulas_from_public_links(
                    planner_base_url=base,
                    planner_client_id=planner_client_id,
                    link_ids=link_ids,
                    client=client,
                    cache=cache,
                    source_url=source_url,
                    building_map=edifici_map,
                )
            )

    if impegni_start and impegni_end and impegni_limit > 0:
        aulas.extend(
            _crawl_planner_aulas_from_impegni(
                planner_base_url=base,
                impegni_start=impegni_start,
                impegni_end=impegni_end,
                impegni_limit=impegni_limit,
                client=client,
                cache=cache,
                source_url=source_url,
                building_map=edifici_map,
            )
        )

    return aulas


def _discover_calendar_link_ids(
    urls: tuple[str, ...],
    client: HttpClient,
    cache: HtmlCache | None,
) -> set[str]:
    link_ids: set[str] = set()
    for url in sorted(set(urls)):
        html_text = _try_fetch_html(url=url, client=client, cache=cache)
        if not html_text:
            continue
        decoded = html.unescape(html_text)
        for match in LINK_CALENDAR_ID_PATTERN.finditer(decoded):
            link_ids.add(match.group(1).lower())
    return link_ids


def _crawl_planner_aulas_from_public_links(
    planner_base_url: str,
    planner_client_id: str,
    link_ids: set[str],
    client: HttpClient,
    cache: HtmlCache | None,
    source_url: str,
    building_map: dict[str, str],
) -> list[RawAula]:
    endpoint = f"{planner_base_url}/api/Aule/getAulePerCalendarioPubblico"
    aulas: list[RawAula] = []

    for link_id in sorted(link_ids):
        payload = {
            "linkCalendarioId": link_id,
            "clienteId": planner_client_id,
        }
        response_text = _try_post_json(url=endpoint, payload=payload, client=client)
        if not response_text:
            continue

        aulas.extend(
            _parse_planner_aula_items(
                payload=response_text,
                source_url=source_url,
                building_map=building_map,
            )
        )

    return aulas


def _crawl_planner_aulas_from_impegni(
    planner_base_url: str,
    impegni_start: str,
    impegni_end: str,
    impegni_limit: int,
    client: HttpClient,
    cache: HtmlCache | None,
    source_url: str,
    building_map: dict[str, str],
) -> list[RawAula]:
    impegni_url = (
        f"{planner_base_url}/api/Impegni/getImpegniPublic"
        f"?dataInizio={impegni_start}&dataFine={impegni_end}&limit={impegni_limit}"
    )
    payload = _try_fetch_html(impegni_url, client=client, cache=cache)
    if not payload:
        return []

    aulas: list[RawAula] = []
    for impegno in _load_json_array(payload):
        raw_aule = impegno.get("aule")
        if not isinstance(raw_aule, list):
            continue

        for item in raw_aule:
            if not isinstance(item, dict):
                continue

            descrizione = _normalize_text(str(item.get("descrizione") or ""))
            codice = _normalize_text(str(item.get("codice") or ""))
            candidate_name = _canonical_planner_aula_name(descrizione or codice)
            if not candidate_name:
                continue

            edificio = item.get("edificio")
            building_hint = None
            if isinstance(edificio, dict):
                building_hint = _normalize_text(str(edificio.get("descrizione") or ""))
            if not building_hint:
                edificio_id = item.get("edificioId")
                if isinstance(edificio_id, str):
                    building_hint = building_map.get(edificio_id)

            aulas.append(
                RawAula(
                    name=candidate_name,
                    source_url=source_url,
                    room=_extract_room_label(candidate_name),
                    short_code=_extract_short_code(candidate_name),
                    building_hint=building_hint,
                )
            )

    return aulas


def _parse_planner_aula_items(
    payload: str,
    source_url: str,
    building_map: dict[str, str],
) -> list[RawAula]:
    aulas: list[RawAula] = []
    for item in _load_json_array(payload):
        descrizione = _normalize_text(str(item.get("descrizione") or ""))
        codice = _normalize_text(str(item.get("codice") or ""))
        candidate_name = _canonical_planner_aula_name(descrizione or codice)
        if not candidate_name:
            continue

        edificio = item.get("edificio")
        building_hint = None
        if isinstance(edificio, dict):
            building_hint = _normalize_text(str(edificio.get("descrizione") or ""))
        if not building_hint:
            edificio_id = item.get("edificioId")
            if isinstance(edificio_id, str):
                building_hint = building_map.get(edificio_id)

        floor = _extract_floor_label(descrizione or "")
        aulas.append(
            RawAula(
                name=candidate_name,
                source_url=source_url,
                room=_extract_room_label(candidate_name),
                short_code=_extract_short_code(candidate_name),
                floor=floor,
                building_hint=building_hint,
            )
        )
    return aulas


def _dedupe_aulas(aulas: list[RawAula]) -> list[RawAula]:
    unique_by_key: dict[tuple[str, str | None], RawAula] = {}
    for aula in aulas:
        key = (
            collapse_whitespace(aula.name).casefold(),
            aula.building_hint.casefold() if aula.building_hint else None,
        )
        existing = unique_by_key.get(key)
        if existing is None:
            unique_by_key[key] = aula
            continue
        unique_by_key[key] = _merge_aula_records(existing=existing, candidate=aula)

    return sorted(
        unique_by_key.values(),
        key=lambda item: (
            item.name.casefold(),
            item.floor.casefold() if item.floor else "",
            item.building_hint.casefold() if item.building_hint else "",
        ),
    )


def _aula_quality_score(aula: RawAula) -> int:
    score = 0
    if aula.lat is not None and aula.lng is not None:
        score += 3
    if aula.building_hint:
        score += 2
    if aula.floor:
        score += 2
    if aula.short_code:
        score += 1
    if aula.room:
        score += 1
    if aula.capacity is not None:
        score += 1
    return score


def _merge_aula_records(existing: RawAula, candidate: RawAula) -> RawAula:
    primary = existing if _aula_quality_score(existing) >= _aula_quality_score(candidate) else candidate
    secondary = candidate if primary is existing else existing
    if primary.capacity is None:
        merged_capacity = secondary.capacity
    elif secondary.capacity is None:
        merged_capacity = primary.capacity
    else:
        merged_capacity = max(primary.capacity, secondary.capacity)

    return RawAula(
        name=primary.name,
        source_url=primary.source_url,
        lat=primary.lat if primary.lat is not None else secondary.lat,
        lng=primary.lng if primary.lng is not None else secondary.lng,
        floor=primary.floor or secondary.floor,
        room=primary.room or secondary.room,
        short_code=primary.short_code or secondary.short_code,
        building_hint=primary.building_hint or secondary.building_hint,
        capacity=merged_capacity,
    )


def _fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str:
    if cache is None:
        return client.get_text(url)
    return cache.get_or_fetch(url, client.get_text)


def _try_fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str | None:
    try:
        return _fetch_html(url, client, cache)
    except Exception:
        return None


def _try_post_json(url: str, payload: dict[str, object], client: HttpClient) -> str | None:
    try:
        return client.post_json(url=url, payload=payload)
    except Exception:
        return None


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

    return aulas


def _parse_department_aulas_html(html_text: str, source_url: str) -> list[RawAula]:
    soup = BeautifulSoup(html_text, "html.parser")
    aulas: list[RawAula] = []

    for table in soup.select("table"):
        rows = [
            [cell for cell in (_normalize_text(node.get_text(" ", strip=True)) for node in tr.select("th, td")) if cell]
            for tr in table.select("tr")
        ]
        rows = [row for row in rows if row]
        if not rows:
            continue

        header_cells: list[str] | None = rows[0] if _is_table_header_row(rows[0]) else None
        data_rows = rows[1:] if header_cells else rows
        name_indexes = _find_column_indexes(header_cells, ("aula", "nome", "denominazione", "laboratorio"))
        location_indexes = _find_column_indexes(
            header_cells,
            ("cubo", "ubicazione", "luogo", "posizione", "indirizzo", "piano", "liv"),
        )
        capacity_indexes = _find_column_indexes(header_cells, ("capienza", "posti"))

        for cells in data_rows:
            if _is_table_header_row(cells):
                continue

            row_text = collapse_whitespace(" ".join(cells))
            if not row_text:
                continue
            if any(token in row_text.casefold() for token in ("wi-fi", "rete lan", "dotazione")) and "aula" not in row_text.casefold():
                continue

            name_values = _pick_row_values(cells, name_indexes) or [cells[0]]
            location_values = _pick_row_values(cells, location_indexes)
            capacity_values = _pick_row_values(cells, capacity_indexes)

            location_text = collapse_whitespace(" ".join(location_values))
            hint_text = collapse_whitespace(" ".join(location_values or cells[1:3])) or row_text
            building_hint = _extract_building_hint(hint_text)
            floor = _extract_floor_label(hint_text)
            capacity = _extract_capacity(" ".join(capacity_values) or row_text)

            for candidate in _extract_department_candidates(" ; ".join(name_values)):
                canonical_name = _canonical_department_aula_name(candidate)
                if not canonical_name:
                    continue

                room = _extract_room_label(canonical_name)
                short_code = _extract_short_code(canonical_name)
                aulas.append(
                    RawAula(
                        name=canonical_name,
                        source_url=source_url,
                        floor=floor,
                        room=room,
                        short_code=short_code,
                        building_hint=building_hint,
                        capacity=capacity,
                    )
                )

            if not name_indexes and not _contains_aula_signal(name_values):
                continue
            fallback_name = _canonical_department_aula_name(name_values[0])
            if not fallback_name:
                continue
            if any(
                existing.name.casefold() == fallback_name.casefold()
                and existing.source_url == source_url
                and (existing.building_hint or "") == (building_hint or "")
                for existing in aulas
            ):
                continue

            aulas.append(
                RawAula(
                    name=fallback_name,
                    source_url=source_url,
                    floor=floor,
                    room=_extract_room_label(fallback_name),
                    short_code=_extract_short_code(fallback_name),
                    building_hint=building_hint,
                    capacity=capacity,
                )
            )

    aulas.extend(_parse_department_aulas_accordions(soup=soup, source_url=source_url))
    return aulas


def _is_table_header_row(cells: list[str]) -> bool:
    if len(cells) < 2:
        return False
    header_tokens = {"aula", "cubo", "ubicazione", "capienza", "dotazione", "posti", "attrezzature", "nome", "denominazione"}
    lowered = [cell.casefold() for cell in cells]
    token_hits = sum(1 for cell in lowered if any(token in cell for token in header_tokens))
    if token_hits == 0:
        return False
    if any(":" in cell for cell in cells):
        return False
    if any(re.search(r"\b\d{1,4}\b", cell) for cell in cells):
        return False
    if any(len(cell) > 40 for cell in cells):
        return False
    return True


def _find_column_indexes(headers: list[str] | None, tokens: tuple[str, ...]) -> list[int]:
    if not headers:
        return []
    indexes: list[int] = []
    lowered = [header.casefold() for header in headers]
    for idx, value in enumerate(lowered):
        if any(token in value for token in tokens):
            indexes.append(idx)
    return indexes


def _pick_row_values(cells: list[str], indexes: list[int]) -> list[str]:
    values: list[str] = []
    for idx in indexes:
        if idx < len(cells) and cells[idx]:
            values.append(cells[idx])
    return values


def _contains_aula_signal(values: list[str]) -> bool:
    merged = collapse_whitespace(" ".join(values))
    if not merged:
        return False
    lowered = merged.casefold()
    if "aula" in lowered:
        return True
    if _looks_like_room_code(merged):
        return True
    return bool(re.search(r"\b\d{1,2}[A-Za-z]\s*\d?[A-Za-z]?\b", merged))


def _parse_department_aulas_accordions(soup: BeautifulSoup, source_url: str) -> list[RawAula]:
    aulas: list[RawAula] = []
    for item in soup.select(".accordion-item"):
        button = item.select_one("button.accordion-button")
        accordion_title = _normalize_text(button.get_text(" ", strip=True)) if button is not None else None

        body = item.select_one(".accordion-body")
        if body is not None:
            aulas.extend(
                _parse_department_accordion_body_entries(
                    body=body,
                    source_url=source_url,
                    accordion_title=accordion_title,
                )
            )

        if button is None:
            continue
        title = accordion_title
        if not title:
            continue
        if _is_generic_accordion_heading(title):
            continue
        lowered_title = title.casefold()
        if not (
            _contains_aula_signal([title])
            or "laboratorio" in lowered_title
            or "aula studio" in lowered_title
        ):
            continue

        canonical_name = _canonical_department_aula_name(title)
        if not canonical_name:
            continue

        body = item.select_one(".accordion-body")
        body_text = _normalize_text(body.get_text(" ", strip=True)) if body else None
        hint_text = collapse_whitespace(" ".join(part for part in (body_text or "", title) if part))
        body_hint = _extract_building_hint(body_text or "")
        title_hint = _extract_building_hint(title)
        building_hint = body_hint or title_hint
        building_hint = _infer_building_hint_from_name(canonical_name, building_hint)

        aulas.append(
            RawAula(
                name=canonical_name,
                source_url=source_url,
                floor=_extract_floor_label(hint_text),
                room=_extract_room_label(canonical_name),
                short_code=_extract_short_code(canonical_name),
                building_hint=building_hint,
                capacity=_extract_capacity(hint_text),
            )
        )
    return aulas


def _parse_department_accordion_body_entries(
    body: Tag,
    source_url: str,
    accordion_title: str | None = None,
) -> list[RawAula]:
    aulas: list[RawAula] = []
    in_laboratory_section = "laborator" in (accordion_title or "").casefold()
    blocks = [child for child in body.children if isinstance(child, Tag)]
    idx = 0
    while idx < len(blocks):
        entry_titles = _extract_accordion_entry_titles(
            blocks[idx],
            in_laboratory_section=in_laboratory_section,
        )
        if not entry_titles:
            idx += 1
            continue

        detail_parts = [_normalize_text(blocks[idx].get_text(" ", strip=True))]
        cursor = idx + 1
        while cursor < len(blocks):
            if _extract_accordion_entry_titles(
                blocks[cursor],
                in_laboratory_section=in_laboratory_section,
            ):
                break
            detail_parts.append(_normalize_text(blocks[cursor].get_text(" ", strip=True)))
            cursor += 1

        hint_text = collapse_whitespace(" ".join(part for part in detail_parts if part))
        for entry_title in entry_titles:
            canonical_name = _canonical_department_aula_name(entry_title)
            if not canonical_name:
                continue

            body_hint = _extract_building_hint(hint_text)
            title_hint = _extract_building_hint(entry_title)
            building_hint = _infer_building_hint_from_name(canonical_name, body_hint or title_hint)
            floor = _extract_floor_label(hint_text)
            capacity = _extract_capacity(hint_text)

            if (
                in_laboratory_section
                and canonical_name.casefold().startswith("laboratorio di ")
                and not (building_hint or floor or capacity)
            ):
                # Skip broad laboratory headings with no actionable location/capacity details.
                continue

            aulas.append(
                RawAula(
                    name=canonical_name,
                    source_url=source_url,
                    floor=floor,
                    room=_extract_room_label(canonical_name),
                    short_code=_extract_short_code(canonical_name),
                    building_hint=building_hint,
                    capacity=capacity,
                )
            )

        idx = cursor

    return aulas


def _extract_accordion_entry_titles(
    block: Tag,
    in_laboratory_section: bool = False,
) -> list[str]:
    block_text = _normalize_text(block.get_text(" ", strip=True))
    if not block_text:
        return []
    if _is_generic_accordion_heading(block_text):
        return []

    candidates: list[str] = []
    lowered_text = block_text.casefold()

    if block.name == "h4":
        if lowered_text.startswith("laboratorio "):
            candidates.append(block_text)
        elif in_laboratory_section and _is_likely_laboratory_heading(block_text):
            prefix = "Laboratorio " if lowered_text.startswith("di ") else "Laboratorio di "
            candidates.append(f"{prefix}{block_text}")

    for strong in block.find_all("strong"):
        strong_text = _normalize_text(strong.get_text(" ", strip=True))
        if not strong_text:
            continue
        strong_text = strong_text.lstrip("'`\"").strip()
        if not _is_likely_accordion_entry_name(strong_text):
            continue
        if _contains_location_marker(block_text) and not strong_text.casefold().startswith(("aula ", "laboratorio ")):
            continue
        candidates.append(strong_text)

    if not candidates and block.name == "p" and ("aula" in lowered_text or "laboratorio" in lowered_text):
        for candidate in _extract_department_candidates(block_text):
            candidate = candidate.lstrip("'`\"").strip()
            if not candidate.casefold().startswith(("aula ", "laboratorio ")):
                continue
            if not _is_likely_accordion_entry_name(candidate):
                continue
            candidates.append(candidate)

    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = collapse_whitespace(candidate).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)
    return unique_candidates


def _is_likely_accordion_entry_name(value: str) -> bool:
    cleaned = collapse_whitespace(value)
    if not cleaned:
        return False
    lowered = cleaned.casefold()
    if _is_generic_accordion_heading(cleaned):
        return False
    if lowered.startswith("aula "):
        return True
    if lowered.startswith("laboratorio "):
        return True
    return _looks_like_room_code(cleaned)


def _is_likely_laboratory_heading(value: str) -> bool:
    cleaned = collapse_whitespace(value)
    if not cleaned or _is_generic_accordion_heading(cleaned):
        return False
    if len(cleaned) > 80:
        return False
    if ":" in cleaned:
        return False
    lowered = cleaned.casefold()
    if lowered.startswith(("responsabile", "preposto", "dotazione", "capienza", "ubicazione", "collocazione")):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,_'()/\-]*", cleaned))


def _contains_location_marker(text: str) -> bool:
    lowered = text.casefold()
    return any(token in lowered for token in ("ubicazione", "collocazione", "capienza", "posti", "attrezzature"))


def _is_generic_accordion_heading(text: str) -> bool:
    lowered = collapse_whitespace(text).casefold()
    return (
        lowered.startswith("aule per ")
        or lowered.startswith("aule convegni")
        or lowered.startswith("laboratori didattici")
        or lowered.startswith("descrizione dei laboratori")
        or lowered.startswith("aule del dipartimento")
    )


def _extract_department_candidates(value: str) -> list[str]:
    cleaned = collapse_whitespace(value)
    if not cleaned:
        return []

    explicit_matches = [
        collapse_whitespace(match.group(0))
        for match in re.finditer(r"\bAula\s+[A-Za-z0-9][A-Za-z0-9'()\- ]{0,40}", cleaned, flags=re.IGNORECASE)
    ]
    if explicit_matches:
        return explicit_matches

    candidates: list[str] = []
    for token in re.split(r"\s*[;,/|]\s*", cleaned):
        token = collapse_whitespace(token)
        if not token:
            continue
        if _looks_like_room_code(token):
            candidates.append(token)
    if candidates:
        return candidates

    if _looks_like_room_code(cleaned):
        return [cleaned]

    inline_code_matches = [
        collapse_whitespace(match.group(0))
        for match in re.finditer(r"\b\d{1,2}[A-Za-z]\s*\d{0,2}[A-Za-z]?\b", cleaned)
    ]
    if inline_code_matches:
        return inline_code_matches

    return []


def _looks_like_room_code(value: str) -> bool:
    compact = re.sub(r"\s+", "", value).upper()
    if not compact:
        return False
    if len(compact) > 10:
        return False

    if re.fullmatch(r"[A-Z]{1,4}\d{1,4}[A-Z]?", compact):
        return True
    if re.fullmatch(r"\d{1,2}[A-Z]\d{0,2}[A-Z]?", compact):
        return True
    if re.fullmatch(r"[A-Z]\d{1,3}", compact):
        return True
    return False


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
    return "aula " in lowered


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


def _canonical_external_aula_name(name: str | None) -> str | None:
    cleaned = none_if_empty(collapse_whitespace((name or "").replace("\xa0", " ")))
    if not cleaned:
        return None

    lowered = cleaned.casefold()
    if any(token in lowered for token in NOISE_AULA_TOKENS):
        return None

    if lowered.startswith("aula "):
        return _canonical_aula_name(cleaned)

    if "aula " in lowered:
        match = re.search(r"\bAula\s+[A-Za-z0-9][A-Za-z0-9'()\- ]{0,40}", cleaned, flags=re.IGNORECASE)
        if match:
            return _canonical_aula_name(match.group(0))

    if _looks_like_room_code(cleaned):
        return f"Aula {re.sub(r'\s+', '', cleaned).upper()}"

    return None


def _canonical_department_aula_name(name: str | None) -> str | None:
    cleaned = none_if_empty(collapse_whitespace((name or "").replace("\xa0", " ")))
    if not cleaned:
        return None

    cleaned = re.sub(r"^[A-Z]{2,8}\s+(?=\d{1,2}[A-Za-z])", "", cleaned)
    cleaned = collapse_whitespace(cleaned)

    lowered = cleaned.casefold()
    if lowered.startswith("laboratorio "):
        return cleaned

    canonical_external = _canonical_external_aula_name(cleaned)
    if canonical_external:
        return canonical_external

    if any(token in lowered for token in NOISE_AULA_TOKENS):
        return None
    if len(cleaned) > 80:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,_'()/\-]*", cleaned):
        return None
    return f"Aula {cleaned}"


def _canonical_planner_aula_name(name: str | None) -> str | None:
    cleaned = none_if_empty(collapse_whitespace((name or "").replace("\xa0", " ")))
    if not cleaned:
        return None

    lowered = cleaned.casefold()
    if any(token in lowered for token in NOISE_AULA_TOKENS):
        return None

    canonical_external = _canonical_external_aula_name(cleaned)
    if canonical_external:
        return canonical_external

    if len(cleaned) > 100:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,_'()/\-]*", cleaned):
        return None

    # Public planner endpoint already returns aula resources; keep labels as-is.
    return cleaned


def _extract_capacity(text: str) -> int | None:
    cleaned = collapse_whitespace(text)
    if not cleaned:
        return None

    explicit = re.search(
        r"\b(?:capienza|posti|n[°º.]?\s*posti)\s*[:\-]?\s*([0-9]{1,4})\b",
        cleaned,
        flags=re.IGNORECASE,
    )
    if explicit:
        value = int(explicit.group(1))
        return value if 1 <= value <= 5000 else None

    benches_or_workstations = re.search(
        r"\b(?:dotat[oa]\s+di\s+)?([0-9]{1,4})\s*(?:banchi\s+di\s+lavoro|postazioni)\b",
        cleaned,
        flags=re.IGNORECASE,
    )
    if benches_or_workstations:
        value = int(benches_or_workstations.group(1))
        return value if 1 <= value <= 5000 else None

    if re.fullmatch(r"[0-9]{1,4}", cleaned):
        value = int(cleaned)
        return value if 1 <= value <= 5000 else None

    return None


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
    cubo_match = re.search(
        r"\bCubo\s+([0-9]{1,2})(?:\s*[-/]\s*|\s+)?([A-Za-z])?\b",
        text,
        flags=re.IGNORECASE,
    )
    if cubo_match:
        number = cubo_match.group(1)
        letter = cubo_match.group(2)
        suffix = f"{number}{letter.upper() if letter else ''}"
        return f"Cubo {suffix}"

    cubi_match = re.search(
        r"\bCubi\s+([0-9]{1,2}(?:-[0-9]{1,2})?[A-Za-z])\b",
        text,
        flags=re.IGNORECASE,
    )
    if cubi_match:
        return f"Cubi {cubi_match.group(1).upper()}"

    capannone_match = re.search(r"\bCapannone\s+([A-Za-z])\b", text, flags=re.IGNORECASE)
    if capannone_match:
        return f"Capannone {capannone_match.group(1).upper()}"

    if re.search(r"\bAmpliamento\s+Polifunzionale\b", text, flags=re.IGNORECASE):
        return "Ampliamento Polifunzionale"

    if re.search(r"\bOrto\s+Botanico\b", text, flags=re.IGNORECASE):
        return "Orto Botanico"

    if re.search(r"\bPolifunzionale\s+(Ovest|Est)\b", text, flags=re.IGNORECASE):
        match = re.search(r"\bPolifunzionale\s+(Ovest|Est)\b", text, flags=re.IGNORECASE)
        if match:
            return f"Polifunzionale {match.group(1).capitalize()}"
    if re.search(r"\bPolifunzionale\b", text, flags=re.IGNORECASE):
        return "Polifunzionale"

    compact = none_if_empty(re.sub(r"\s+", "", text))
    if compact and re.fullmatch(r"[0-9]{1,2}[A-Za-z]", compact):
        return f"Cubo {compact.upper()}"
    token_match = re.search(r"\b([0-9]{1,2}[A-Za-z])\b", text)
    lowered = text.casefold()
    if token_match and any(token in lowered for token in ("piano", "ponte", "ubicazione", "posizione", "luogo", "cubo")):
        return f"Cubo {token_match.group(1).upper()}"

    return None


def _infer_building_hint_from_name(name: str, building_hint: str | None) -> str | None:
    if building_hint and re.fullmatch(r"Cubo\s+[0-9]{1,2}[A-Za-z]", building_hint):
        return building_hint

    upper_name = name.upper()
    match = re.search(
        r"\b(?:CH-)?([0-9]{1,2})-[0-9]{1,2}([A-Z])(?:-[0-9]{1,2}[A-Z])?\b",
        upper_name,
    )
    if not match:
        return building_hint

    inferred = f"Cubo {int(match.group(1))}{match.group(2)}"
    if building_hint and re.fullmatch(r"Cubo\s+[0-9]{1,2}", building_hint):
        return inferred
    if building_hint:
        return building_hint
    return inferred


def _extract_floor_label(text: str) -> str | None:
    cleaned = collapse_whitespace(text)
    if not cleaned:
        return None

    lowered = cleaned.casefold()
    for label in FLOOR_LABELS:
        if label.casefold() in lowered:
            return label

    word_match = re.search(
        r"\b(terra|primo|secondo|terzo|quarto|quinto|sesto|settimo)\s+piano\b",
        lowered,
    )
    if word_match:
        label = FLOOR_WORD_TO_LABEL.get(word_match.group(1))
        if label:
            return label

    reversed_word_match = re.search(
        r"\bpiano\s+(terra|primo|secondo|terzo|quarto|quinto|sesto|settimo)\b",
        lowered,
    )
    if reversed_word_match:
        label = FLOOR_WORD_TO_LABEL.get(reversed_word_match.group(1))
        if label:
            return label

    numeric_match = re.search(r"\bpiano\s+([ivxlcdm]+|[0-9]+)\b", lowered)
    if not numeric_match:
        return None

    value = numeric_match.group(1)
    numeric_value: int | None = None
    if value.isdigit():
        numeric_value = int(value)
    else:
        numeric_value = _roman_to_int(value.upper())

    if numeric_value is None:
        return None
    if numeric_value == 0:
        return "Piano Terra"
    by_index = {
        1: "Primo piano",
        2: "Secondo piano",
        3: "Terzo piano",
        4: "Quarto piano",
        5: "Quinto piano",
        6: "Sesto piano",
        7: "Settimo piano",
    }
    return by_index.get(numeric_value)


def _roman_to_int(value: str) -> int | None:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for char in reversed(value):
        current = values.get(char)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total


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


def _load_json_array(payload: str | None) -> list[dict[str, object]]:
    if not payload:
        return []

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _load_json_object(payload: str | None) -> dict[str, object] | None:
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return parsed
    return None


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
