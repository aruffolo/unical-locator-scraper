"""Normalization layer from raw extraction to canonical JSON entities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import math
from pathlib import Path
import re

from ..extract.aulas import RawAula
from ..extract.buildings import RawBuilding
from ..extract.departments import RawDepartment
from ..extract.services import RawService
from ..extract.teachers import RawTeacher
from ..utils.text import collapse_whitespace, none_if_empty, slugify
from .dedupe import dedupe_people
from .ids import (
    make_aula_id,
    make_building_id,
    make_department_id,
    make_person_id,
    make_place_id,
)


def normalize_teachers(
    raw_teachers: list[RawTeacher],
    source_id: str = "unical-teachers",
    verified_at: datetime | None = None,
) -> list[dict[str, str]]:
    """Convert raw teachers to canonical `people.json` records.

    Output follows `data/schema/people.schema.json` and ER constraints.
    """
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)

    verified_iso = verified_at.isoformat()

    normalized: list[dict[str, str]] = []
    for raw in raw_teachers:
        full_name = none_if_empty(collapse_whitespace(raw.full_name))
        if not full_name:
            continue

        person: dict[str, str] = {
            "person_id": make_person_id(full_name=full_name, email=raw.email),
            "full_name": full_name,
            "role": "PROFESSOR",
            "source_id": source_id,
            "source_url": raw.source_url,
            "last_verified_at": verified_iso,
        }

        if raw.email:
            person["email"] = raw.email.lower().strip()
        if raw.phone:
            person["phone"] = raw.phone.strip()
        if raw.department_name:
            person["department_id"] = make_department_id(raw.department_name)
        if raw.website_url:
            person["website_url"] = raw.website_url.strip()
        if raw.office_hours:
            person["office_hours"] = collapse_whitespace(raw.office_hours)
        if raw.notes:
            person["notes"] = collapse_whitespace(raw.notes)

        normalized.append(person)

    deduped = dedupe_people(normalized)
    return sorted(deduped, key=lambda person: person["person_id"])


def normalize_departments(
    raw_departments: list[RawDepartment],
    source_id: str = "unical-departments",
    verified_at: datetime | None = None,
) -> list[dict[str, str]]:
    """Convert raw departments to canonical `departments.json` records."""
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)

    verified_iso = verified_at.isoformat()
    unique_by_id: dict[str, dict[str, str]] = {}

    for raw in raw_departments:
        name = none_if_empty(collapse_whitespace(raw.name))
        if not name:
            continue

        department_id = make_department_id(name)
        department: dict[str, str] = {
            "department_id": department_id,
            "name": name,
            "source_id": source_id,
            "source_url": raw.source_url,
            "last_verified_at": verified_iso,
        }

        if raw.email:
            department["email"] = raw.email.lower().strip()
        if raw.phone:
            department["phone"] = collapse_whitespace(raw.phone)
        if raw.website_url:
            department["website_url"] = raw.website_url.strip()

        unique_by_id.setdefault(department_id, department)

    return sorted(unique_by_id.values(), key=lambda department: department["department_id"])


def normalize_services(
    raw_services: list[RawService],
    source_id: str = "unical-services",
    verified_at: datetime | None = None,
) -> list[dict[str, str]]:
    """Convert raw services to canonical `places.json` records."""
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)

    verified_iso = verified_at.isoformat()
    unique_by_id: dict[str, dict[str, str]] = {}

    for raw in raw_services:
        name = none_if_empty(collapse_whitespace(raw.name))
        if not name:
            continue

        place_type = raw.service_type if raw.service_type else "SERVICE"
        place = {
            "place_id": make_place_id(name=name, place_type=place_type),
            "type": place_type,
            "name": name,
            "source_id": source_id,
            "source_url": raw.source_url,
            "last_verified_at": verified_iso,
        }

        if raw.description:
            place["description"] = collapse_whitespace(raw.description)
        if raw.email:
            place["email"] = raw.email.lower().strip()
        if raw.phone:
            place["phone"] = collapse_whitespace(raw.phone)
        if raw.website_url:
            place["access_notes"] = f"Sito: {raw.website_url.strip()}"
        if raw.opening_hours:
            place["opening_hours"] = collapse_whitespace(raw.opening_hours)

        unique_by_id.setdefault(place["place_id"], place)

    return sorted(unique_by_id.values(), key=lambda place: place["place_id"])


def normalize_buildings(
    raw_buildings: list[RawBuilding],
    source_id: str = "unical-campus-map",
    verified_at: datetime | None = None,
) -> list[dict[str, str | float]]:
    """Convert raw buildings to canonical `buildings.json` records."""
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)

    verified_iso = verified_at.isoformat()
    unique_by_id: dict[str, dict[str, str | float]] = {}

    for raw in raw_buildings:
        name = _canonical_building_name(raw.name)
        if not name:
            continue

        building_id = make_building_id(name)
        building: dict[str, str | float] = {
            "building_id": building_id,
            "name": name,
            "lat": round(raw.lat, 7),
            "lng": round(raw.lng, 7),
            "source_id": source_id,
            "source_url": raw.source_url,
            "last_verified_at": verified_iso,
        }
        if raw.description:
            building["description"] = collapse_whitespace(raw.description)

        unique_by_id.setdefault(building_id, building)

    return sorted(unique_by_id.values(), key=lambda item: str(item["building_id"]))


def normalize_aulas(
    raw_aulas: list[RawAula],
    buildings: list[dict[str, object]] | None = None,
    source_id: str = "unical-aulas",
    verified_at: datetime | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Convert raw aulas into `aulas.json` and matching AULA `places.json` records."""
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)

    verified_iso = verified_at.isoformat()
    buildings = buildings or []

    building_ids = {
        str(item.get("building_id")) for item in buildings if isinstance(item.get("building_id"), str)
    }
    buildings_with_coordinates: list[tuple[str, float, float]] = []
    for item in buildings:
        building_id = item.get("building_id")
        lat = item.get("lat")
        lng = item.get("lng")
        if not isinstance(building_id, str):
            continue
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            buildings_with_coordinates.append((building_id, float(lat), float(lng)))

    aulas_by_id: dict[str, dict[str, object]] = {}
    places_by_id: dict[str, dict[str, object]] = {}

    for raw in raw_aulas:
        name = none_if_empty(collapse_whitespace(raw.name))
        if not name:
            continue

        normalized_name = _normalize_aula_name(name)
        short_code = _normalize_short_code(raw.short_code)
        room = none_if_empty(collapse_whitespace(raw.room))
        floor = none_if_empty(collapse_whitespace(raw.floor))
        capacity = raw.capacity if isinstance(raw.capacity, int) and raw.capacity > 0 else None
        building_id = _resolve_aula_building_id(
            building_hint=raw.building_hint,
            lat=raw.lat,
            lng=raw.lng,
            known_building_ids=building_ids,
            buildings_with_coordinates=buildings_with_coordinates,
        )

        aula_id = make_aula_id(name=normalized_name, building_id=building_id, short_code=short_code)
        place_id = aula_id
        search_tokens = _build_aula_search_tokens(
            name=name,
            normalized_name=normalized_name,
            short_code=short_code,
            room=room,
            building_id=building_id,
        )

        aula: dict[str, object] = {
            "aula_id": aula_id,
            "place_id": place_id,
            "name": name,
            "normalized_name": normalized_name,
            "search_tokens": search_tokens,
            "source_id": source_id,
            "source_url": raw.source_url,
            "last_verified_at": verified_iso,
        }
        if short_code:
            aula["short_code"] = short_code
        if building_id:
            aula["building_id"] = building_id
        if floor:
            aula["floor"] = floor
        if room:
            aula["room"] = room
        if capacity is not None:
            aula["capacity"] = capacity

        place: dict[str, object] = {
            "place_id": place_id,
            "type": "AULA",
            "name": name,
            "source_id": source_id,
            "source_url": raw.source_url,
            "last_verified_at": verified_iso,
        }
        if building_id:
            place["building_id"] = building_id
        if floor:
            place["floor"] = floor
        if room:
            place["room"] = room
        if raw.lat is not None and raw.lng is not None:
            place["lat"] = round(raw.lat, 7)
            place["lng"] = round(raw.lng, 7)

        aulas_by_id.setdefault(aula_id, aula)
        places_by_id.setdefault(place_id, place)

    aulas = sorted(aulas_by_id.values(), key=lambda item: str(item["aula_id"]))
    aula_places = sorted(places_by_id.values(), key=lambda item: str(item["place_id"]))
    _backfill_missing_aula_buildings(
        aulas=aulas,
        aula_places=aula_places,
        known_building_ids=building_ids,
    )
    return aulas, aula_places


def _canonical_building_name(name: str) -> str | None:
    cleaned = none_if_empty(collapse_whitespace(name.replace("\xa0", " ")))
    if not cleaned:
        return None

    match = re.match(r"^(Cubo\s+[0-9A-Z]+|Cubi\s+[0-9A-Z-]+[A-Z]?)(?:\s|-|$)", cleaned, flags=re.IGNORECASE)
    if match:
        canonical = collapse_whitespace(match.group(1))
        if canonical.lower().startswith("cubo "):
            suffix = canonical.split(" ", maxsplit=1)[1]
            return f"Cubo {suffix.upper()}"
        if canonical.lower().startswith("cubi "):
            suffix = canonical.split(" ", maxsplit=1)[1]
            return f"Cubi {suffix.upper()}"

    return cleaned


def _normalize_aula_name(name: str) -> str:
    normalized = collapse_whitespace(name.replace("\xa0", " "))
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.casefold()


def _normalize_short_code(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", "", value)
    compact = compact.strip().upper()
    if not compact:
        return None
    return compact


def _build_aula_search_tokens(
    name: str,
    normalized_name: str,
    short_code: str | None,
    room: str | None,
    building_id: str | None,
) -> list[str]:
    tokens: set[str] = set()

    for value in [name, normalized_name]:
        slug = slugify(value)
        if slug:
            tokens.add(slug)
            tokens.add(slug.replace("-", ""))

    if name.casefold().startswith("aula "):
        without_prefix = name[5:]
        slug = slugify(without_prefix)
        if slug:
            tokens.add(slug)
            tokens.add(slug.replace("-", ""))

    if short_code:
        tokens.add(short_code.casefold())
    if room:
        slug = slugify(room)
        if slug:
            tokens.add(slug)
            tokens.add(slug.replace("-", ""))
    if building_id:
        tokens.add(building_id.casefold())

    return sorted(token for token in tokens if token)


def _resolve_aula_building_id(
    building_hint: str | None,
    lat: float | None,
    lng: float | None,
    known_building_ids: set[str],
    buildings_with_coordinates: list[tuple[str, float, float]],
) -> str | None:
    if building_hint:
        candidate = make_building_id(building_hint)
        if candidate in known_building_ids:
            return candidate

    if lat is None or lng is None or not buildings_with_coordinates:
        return None

    nearest: tuple[str, float] | None = None
    for building_id, building_lat, building_lng in buildings_with_coordinates:
        distance = _haversine_meters(lat, lng, building_lat, building_lng)
        if nearest is None or distance < nearest[1]:
            nearest = (building_id, distance)

    if nearest is None:
        return None
    if nearest[1] > 250.0:
        return None
    return nearest[0]


def _backfill_missing_aula_buildings(
    aulas: list[dict[str, object]],
    aula_places: list[dict[str, object]],
    known_building_ids: set[str],
) -> None:
    name_to_buildings: dict[str, set[str]] = {}
    room_to_buildings: dict[str, set[str]] = {}
    short_to_buildings: dict[str, set[str]] = {}

    for aula in aulas:
        building_id = aula.get("building_id")
        if not isinstance(building_id, str) or building_id not in known_building_ids:
            continue

        normalized_name = _normalize_lookup_value(aula.get("normalized_name") or aula.get("name"))
        if normalized_name:
            name_to_buildings.setdefault(normalized_name, set()).add(building_id)

        normalized_room = _normalize_lookup_value(aula.get("room"))
        if normalized_room:
            room_to_buildings.setdefault(normalized_room, set()).add(building_id)

        normalized_short = _normalize_lookup_value(aula.get("short_code"))
        if normalized_short:
            short_to_buildings.setdefault(normalized_short, set()).add(building_id)

    place_by_id = {
        str(place.get("place_id")): place
        for place in aula_places
        if isinstance(place.get("place_id"), str)
    }

    for aula in aulas:
        if isinstance(aula.get("building_id"), str):
            continue

        candidates: set[str] = set()

        normalized_name = _normalize_lookup_value(aula.get("normalized_name") or aula.get("name"))
        if normalized_name:
            candidates |= _single_candidate(name_to_buildings, normalized_name)

        normalized_room = _normalize_lookup_value(aula.get("room"))
        if normalized_room:
            candidates |= _single_candidate(room_to_buildings, normalized_room)

        normalized_short = _normalize_lookup_value(aula.get("short_code"))
        if normalized_short:
            candidates |= _single_candidate(short_to_buildings, normalized_short)

        text = " ".join(
            part
            for part in (
                str(aula.get("name") or ""),
                str(aula.get("room") or ""),
                str(aula.get("short_code") or ""),
                str(aula.get("source_url") or ""),
            )
            if part
        )
        candidates |= _extract_building_ids_from_text(text=text, known_building_ids=known_building_ids)

        chosen = next(iter(candidates)) if len(candidates) == 1 else None
        if not chosen:
            continue

        aula["building_id"] = chosen
        existing_tokens = [
            token
            for token in aula.get("search_tokens", [])
            if isinstance(token, str) and token
        ]
        token_set = set(existing_tokens)
        token_set.add(chosen.casefold())
        aula["search_tokens"] = sorted(token_set)

        place_id = aula.get("place_id")
        if isinstance(place_id, str):
            place = place_by_id.get(place_id)
            if place is not None and not isinstance(place.get("building_id"), str):
                place["building_id"] = chosen


def _normalize_lookup_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = none_if_empty(collapse_whitespace(value).casefold())
    return normalized


def _single_candidate(mapping: dict[str, set[str]], key: str) -> set[str]:
    candidates = mapping.get(key, set())
    if len(candidates) == 1:
        return set(candidates)
    return set()


def _extract_building_ids_from_text(text: str, known_building_ids: set[str]) -> set[str]:
    candidates: set[str] = set()
    lowered = collapse_whitespace(text).casefold()
    if not lowered:
        return candidates

    for match in re.finditer(r"\bcubo\s*([0-9]{1,2})(?:\s*[/-]?\s*([a-z]))?\b", lowered):
        number = match.group(1)
        letter = match.group(2) or ""
        building_id = f"cubo-{number}{letter}"
        if building_id in known_building_ids:
            candidates.add(building_id)

    for match in re.finditer(r"\b([0-9]{1,2})\s*([a-z])\b", lowered):
        building_id = f"cubo-{match.group(1)}{match.group(2)}"
        if building_id in known_building_ids:
            candidates.add(building_id)

    if any(token in lowered for token in (" cla ", "centro linguistico", "centro-linguistico")):
        cla_id = "cla-centro-linguistico-d-ateneo"
        if cla_id in known_building_ids:
            candidates.add(cla_id)

    return candidates


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius * c


def write_json(path: Path, payload: object) -> None:
    """Write deterministic JSON files for PR-friendly diffs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
