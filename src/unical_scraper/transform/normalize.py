"""Normalization layer from raw extraction to canonical JSON entities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import math
from pathlib import Path
import re
from urllib.parse import unquote, urlparse

from ..extract.aulas import RawAula
from ..extract.buildings import RawBuilding
from ..extract.departments import RawDepartment
from ..extract.services import RawService
from ..extract.teachers import RawTeacher
from ..utils.text import collapse_whitespace, none_if_empty, person_name_key, slugify
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
    departments: list[dict[str, object]] | None = None,
    department_teacher_map: dict[str, str] | None = None,
    source_id: str = "unical-teachers",
    verified_at: datetime | None = None,
) -> list[dict[str, str]]:
    """Convert raw teachers to canonical `people.json` records.

    Output follows `data/schema/people.schema.json` and ER constraints.
    """
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)

    verified_iso = verified_at.isoformat()
    department_resolver = _DepartmentResolver(departments or [])
    office_place_ids = build_teacher_office_place_ids(raw_teachers)
    department_teacher_map = department_teacher_map or {}

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
            resolved_department_id = department_resolver.resolve(
                raw.department_name,
                email=raw.email,
                website_url=raw.website_url,
            )
            if resolved_department_id:
                person["department_id"] = resolved_department_id
            elif not departments:
                person["department_id"] = make_department_id(raw.department_name)
        elif departments:
            resolved_department_id = department_resolver.resolve(
                "",
                email=raw.email,
                website_url=raw.website_url,
            )
            if resolved_department_id:
                person["department_id"] = resolved_department_id
        if "department_id" not in person and department_teacher_map:
            mapped_department_id = _resolve_department_from_teacher_map(
                raw=raw,
                department_teacher_map=department_teacher_map,
            )
            if mapped_department_id:
                person["department_id"] = mapped_department_id
        if raw.website_url:
            person["website_url"] = raw.website_url.strip()
        if raw.office_hours:
            person["office_hours"] = collapse_whitespace(raw.office_hours)
        office_place_id = office_place_ids.get(_teacher_office_key(raw))
        if office_place_id:
            person["office_place_id"] = office_place_id
        if raw.notes:
            person["notes"] = collapse_whitespace(raw.notes)

        normalized.append(person)

    deduped = dedupe_people(normalized)
    return sorted(deduped, key=lambda person: person["person_id"])


_DEPARTMENT_ACRONYM_RE = re.compile(r"\b([A-Z][A-Za-z]{2,8})\b")
_CUBO_BUILDING_RE = re.compile(r"\bcubo\s*([0-9]{1,2})([a-z])\b", re.IGNORECASE)
_FLOOR_RE = re.compile(r"\bpiano\s*([0-9a-z]+)\b", re.IGNORECASE)
_ROOM_RE = re.compile(r"\bstanza\s*([0-9a-z]+)\b", re.IGNORECASE)


class _DepartmentResolver:
    def __init__(self, departments: list[dict[str, object]]) -> None:
        self._by_id = {
            str(item.get("department_id")): str(item.get("department_id"))
            for item in departments
            if item.get("department_id")
        }
        self._normalized_name_to_id: dict[str, str] = {}
        self._acronym_to_id: dict[str, str] = {}
        self._domain_alias_to_id: dict[str, str] = {}

        for item in departments:
            department_id = item.get("department_id")
            name = item.get("name")
            if not isinstance(department_id, str) or not isinstance(name, str):
                continue
            normalized_name = _normalize_department_name(name)
            if normalized_name:
                self._normalized_name_to_id.setdefault(normalized_name, department_id)
            for acronym in _department_acronyms(name):
                self._acronym_to_id.setdefault(acronym, department_id)
                self._domain_alias_to_id.setdefault(acronym.casefold(), department_id)
            source_url = item.get("source_url")
            if isinstance(source_url, str):
                source_acronym = _department_acronym_from_source_url(source_url)
                if source_acronym:
                    self._acronym_to_id.setdefault(source_acronym, department_id)
                    self._domain_alias_to_id.setdefault(source_acronym.casefold(), department_id)
            for alias in _department_domain_aliases(name):
                self._domain_alias_to_id.setdefault(alias, department_id)

    def resolve(
        self,
        raw_department_name: str,
        email: str | None = None,
        website_url: str | None = None,
    ) -> str | None:
        raw_text = none_if_empty(collapse_whitespace(raw_department_name))
        if raw_text:
            direct_id = make_department_id(raw_text)
            if direct_id in self._by_id:
                return direct_id

            normalized = _normalize_department_name(raw_text)
            if normalized and normalized in self._normalized_name_to_id:
                return self._normalized_name_to_id[normalized]

            raw_upper = raw_text.upper()
            if raw_upper in self._acronym_to_id:
                return self._acronym_to_id[raw_upper]

            for token in _department_acronyms(raw_text):
                if token in self._acronym_to_id:
                    return self._acronym_to_id[token]

        from_domain = self._resolve_from_email_domain(email=email, website_url=website_url)
        if from_domain:
            return from_domain

        return None

    def _resolve_from_email_domain(self, email: str | None, website_url: str | None) -> str | None:
        candidates: list[str] = []
        if email and "@" in email:
            candidates.append(email.split("@", maxsplit=1)[1].casefold())
        if website_url:
            parsed = urlparse(website_url)
            if parsed.netloc:
                candidates.append(parsed.netloc.casefold())

        for domain in candidates:
            alias = _department_alias_from_domain(domain)
            if alias and alias in self._domain_alias_to_id:
                return self._domain_alias_to_id[alias]
        return None


def normalize_teacher_office_places(
    raw_teachers: list[RawTeacher],
    existing_places: list[dict[str, object]],
    buildings: list[dict[str, object]] | None = None,
    source_id: str = "unical-teachers",
    verified_at: datetime | None = None,
) -> list[dict[str, object]]:
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)
    verified_iso = verified_at.isoformat()

    building_ids = {
        str(item.get("building_id"))
        for item in (buildings or [])
        if isinstance(item.get("building_id"), str)
    }
    building_name_slugs = {
        str(item.get("building_id")): slugify(str(item.get("name")))
        for item in (buildings or [])
        if isinstance(item.get("building_id"), str) and isinstance(item.get("name"), str)
    }

    preserved_places = [place for place in existing_places if place.get("source_id") != source_id]
    by_id: dict[str, dict[str, object]] = {
        str(place["place_id"]): dict(place)
        for place in preserved_places
        if isinstance(place, dict) and isinstance(place.get("place_id"), str)
    }

    for raw in raw_teachers:
        office_reference = _extract_teacher_office_reference(raw)
        if not office_reference or not _is_structured_office_reference(office_reference):
            continue

        place_id = _office_place_id_from_reference(office_reference)
        place: dict[str, object] = {
            "place_id": place_id,
            "type": "OFFICE",
            "name": f"Ufficio {office_reference}",
            "source_id": source_id,
            "source_url": raw.source_url,
            "last_verified_at": verified_iso,
        }
        if raw.office_hours:
            place["opening_hours"] = collapse_whitespace(raw.office_hours)
        if raw.notes:
            place["description"] = collapse_whitespace(raw.notes)

        building_id = _infer_office_building_id(
            office_reference,
            known_building_ids=building_ids,
            building_name_slugs=building_name_slugs,
        )
        if building_id:
            place["building_id"] = building_id
        floor = _extract_floor(office_reference)
        if floor:
            place["floor"] = floor
        room = _extract_room(office_reference)
        if room:
            place["room"] = room

        by_id.setdefault(place_id, place)

    return sorted(by_id.values(), key=lambda place: str(place.get("place_id", "")))


def build_teacher_office_place_ids(raw_teachers: list[RawTeacher]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in raw_teachers:
        office_reference = _extract_teacher_office_reference(raw)
        if not office_reference or not _is_structured_office_reference(office_reference):
            continue
        result[_teacher_office_key(raw)] = _office_place_id_from_reference(office_reference)
    return result


def _normalize_department_name(name: str) -> str:
    normalized = slugify(name)
    if not normalized:
        return ""
    for token in ["-dip", "-dipartimento", "-di", "-desf", "-dices", "-diam", "-dimes"]:
        normalized = normalized.replace(token, "")
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized


def _department_acronyms(name: str) -> set[str]:
    acronyms: set[str] = set()
    for match in _DEPARTMENT_ACRONYM_RE.finditer(name):
        token = match.group(1).upper()
        if token.startswith("D") and len(token) >= 4:
            acronyms.add(token)

    if "-" in name:
        suffix = name.rsplit("-", maxsplit=1)[-1].strip().upper()
        suffix = re.sub(r"[^A-Z]", "", suffix)
        if suffix.startswith("D") and len(suffix) >= 4:
            acronyms.add(suffix)

    return acronyms


def _department_domain_aliases(name: str) -> set[str]:
    lowered = name.casefold()
    aliases: set[str] = set()
    if "fisica" in lowered:
        aliases.add("fis")
    return aliases


def _department_acronym_from_source_url(source_url: str) -> str | None:
    candidate = source_url.rstrip("/").rsplit("/", maxsplit=1)[-1].upper()
    candidate = re.sub(r"[^A-Z]", "", candidate)
    if candidate.startswith("D") and len(candidate) >= 4:
        return candidate
    return None


def _department_alias_from_domain(domain: str) -> str | None:
    clean = domain.strip().lstrip("www.")
    if clean.endswith(".unical.it"):
        prefix = clean[: -len(".unical.it")]
        if prefix and "." not in prefix:
            return prefix
    return None


def _teacher_office_key(raw: RawTeacher) -> str:
    return (
        _extract_teacher_office_reference(raw)
        or none_if_empty(collapse_whitespace(raw.full_name))
        or ""
    )


def _resolve_department_from_teacher_map(
    raw: RawTeacher,
    department_teacher_map: dict[str, str],
) -> str | None:
    if raw.department_code:
        code = none_if_empty(raw.department_code.strip())
        if code:
            mapped = department_teacher_map.get(f"department_code:{code}")
            if mapped:
                return mapped

    website_slug = _teacher_profile_slug(raw.website_url or raw.source_url)
    if website_slug:
        mapped = department_teacher_map.get(f"slug:{website_slug}")
        if mapped:
            return mapped
        encoded_slug = _teacher_profile_slug_encoded(website_slug)
        if encoded_slug:
            mapped = department_teacher_map.get(f"slug:{encoded_slug}")
        if mapped:
            return mapped

    if raw.email and "@" in raw.email:
        local_part = none_if_empty(raw.email.split("@", maxsplit=1)[0].strip().casefold())
        if local_part:
            mapped = department_teacher_map.get(f"email_local:{local_part}")
            if mapped:
                return mapped

    normalized_name = none_if_empty(collapse_whitespace(raw.full_name).casefold())
    if normalized_name:
        mapped = department_teacher_map.get(f"name:{normalized_name}")
        if mapped:
            return mapped
    key = person_name_key(raw.full_name)
    if key:
        mapped = department_teacher_map.get(f"name_key:{key}")
        if mapped:
            return mapped
    return None


def _teacher_profile_slug(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/storage/teachers/([^/?#]+)/?", url, flags=re.IGNORECASE)
    if not match:
        return None
    return none_if_empty(unquote(match.group(1)).strip().casefold())


def _teacher_profile_slug_encoded(slug: str) -> str | None:
    if not slug:
        return None
    return none_if_empty(
        re.sub(r"[^a-z0-9._-]", lambda m: f"%{ord(m.group(0)):02x}", slug).casefold()
    )


def _extract_teacher_office_reference(raw: RawTeacher) -> str | None:
    if raw.office_reference:
        return none_if_empty(collapse_whitespace(raw.office_reference))
    if raw.notes:
        match = re.search(r"Office references:\s*([^|]+)", raw.notes, flags=re.IGNORECASE)
        if match:
            return none_if_empty(collapse_whitespace(match.group(1)))
    return None


def _is_structured_office_reference(value: str) -> bool:
    lowered = collapse_whitespace(value).casefold()
    return any(
        token in lowered
        for token in (
            "cubo",
            "piano",
            "stanza",
            "edificio",
            "capannone",
            "polifunzionale",
            "orto botanico",
            "centro sanitario",
            "centro linguistico",
        )
    )


def _office_place_id_from_reference(office_reference: str) -> str:
    return make_place_id(name=f"Ufficio {office_reference}", place_type="OFFICE")


def _infer_office_building_id(
    office_reference: str,
    known_building_ids: set[str],
    building_name_slugs: dict[str, str],
) -> str | None:
    candidates = _extract_building_ids_from_text(
        text=office_reference,
        known_building_ids=known_building_ids,
    )

    lowered_reference = collapse_whitespace(office_reference).casefold()
    if "centro sanitario" in lowered_reference and "centro-sanitario" in known_building_ids:
        candidates.add("centro-sanitario")

    reference_slug = slugify(office_reference)
    if reference_slug:
        for building_id, building_slug in building_name_slugs.items():
            if not building_slug or len(building_slug) < 8:
                continue
            if building_slug in reference_slug:
                candidates.add(building_id)

    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _extract_floor(office_reference: str) -> str | None:
    match = _FLOOR_RE.search(office_reference)
    if not match:
        return None
    return f"Piano {match.group(1)}"


def _extract_room(office_reference: str) -> str | None:
    match = _ROOM_RE.search(office_reference)
    if not match:
        return None
    return f"Stanza {match.group(1)}"


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
    _apply_source_specific_building_overrides(
        aulas=aulas,
        aula_places=aula_places,
        known_building_ids=building_ids,
    )
    _apply_source_specific_aula_enrichments_and_drops(
        aulas=aulas,
        aula_places=aula_places,
        known_building_ids=building_ids,
    )
    deduped_aulas, deduped_places = _collapse_duplicate_aulas(
        aulas=aulas,
        aula_places=aula_places,
    )
    return deduped_aulas, deduped_places


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

        _set_aula_building_id(
            aula=aula,
            building_id=chosen,
            place_by_id=place_by_id,
            force=False,
        )


def _apply_source_specific_building_overrides(
    aulas: list[dict[str, object]],
    aula_places: list[dict[str, object]],
    known_building_ids: set[str],
) -> None:
    place_by_id = {
        str(place.get("place_id")): place
        for place in aula_places
        if isinstance(place.get("place_id"), str)
    }

    for aula in aulas:
        source_url = str(aula.get("source_url") or "").casefold()
        room = str(aula.get("room") or "").strip().upper()
        short_code = str(aula.get("short_code") or "").strip().upper()
        code = short_code or room
        name = str(aula.get("name") or "")
        lowered_name = name.casefold()

        override_building_id: str | None = None

        if "dispes.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if code in {"G1", "G2", "G3", "G4"}:
                override_building_id = "capannone-g"
            elif code in {"H1", "H2", "H3", "H4"}:
                override_building_id = "capannone-h"
            elif code in {"L1", "L2"}:
                override_building_id = "capannone-l"
            elif code in {"LS1", "LS3", "B", "44"}:
                override_building_id = "polifunzionale"

        elif "dfssn.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if code in {"13", "14", "15"}:
                override_building_id = "capannone-c"
            elif code in {"20", "21", "25"}:
                override_building_id = "capannone-d"
            elif code in {"45", "46", "52", "53"}:
                override_building_id = "capannone-f"
            elif "aula circolare" in lowered_name or "aula gialla" in lowered_name or "aula informatica" in lowered_name:
                override_building_id = "polifunzionale-dfssn"
            elif "laboratorio chimico b" in lowered_name or "laboratorio chimico c" in lowered_name:
                override_building_id = "capannone-e"
            elif "microbiologia" in lowered_name:
                override_building_id = "capannone-e"

        elif "dimeg.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if "consolidata b" in lowered_name:
                override_building_id = "cubo-43c"
            elif "ds4" in lowered_name:
                override_building_id = "cubo-41b"
            elif re.search(r"\bp1\b", code.casefold()) and "piano ponte carrabile" in lowered_name:
                override_building_id = "cubo-40c"
            elif lowered_name.startswith("aula m4 - aula seminari"):
                override_building_id = "cubo-44c"

        elif "unical.prod.up.cineca.it/calendar/activities/" in source_url:
            if lowered_name.startswith("aula gialla -"):
                override_building_id = "polifunzionale-dfssn"
            elif "medicina traslazionale" in lowered_name or "seminari medicina" in lowered_name:
                override_building_id = "polifunzionale-dfssn"
            elif "centro di simulazione" in lowered_name and "med-td" in lowered_name:
                override_building_id = "polifunzionale-dfssn"
            elif lowered_name == "aula orto botanico":
                override_building_id = "orto-botanico"
            elif " lingue " in f" {lowered_name} " or lowered_name.endswith(" cla") or lowered_name == "aula cla":
                override_building_id = "cla-centro-linguistico-d-ateneo"

        if not override_building_id or override_building_id not in known_building_ids:
            continue

        _set_aula_building_id(
            aula=aula,
            building_id=override_building_id,
            place_by_id=place_by_id,
            force=True,
        )


def _set_aula_building_id(
    aula: dict[str, object],
    building_id: str,
    place_by_id: dict[str, dict[str, object]],
    force: bool,
) -> None:
    existing_building_id = aula.get("building_id")
    if isinstance(existing_building_id, str) and existing_building_id and not force:
        return

    aula["building_id"] = building_id
    existing_tokens = [
        token
        for token in aula.get("search_tokens", [])
        if isinstance(token, str) and token
    ]
    token_set = set(existing_tokens)
    token_set.add(building_id.casefold())
    aula["search_tokens"] = sorted(token_set)

    place_id = aula.get("place_id")
    if isinstance(place_id, str):
        place = place_by_id.get(place_id)
        if place is not None and (force or not isinstance(place.get("building_id"), str)):
            place["building_id"] = building_id


def _apply_source_specific_aula_enrichments_and_drops(
    aulas: list[dict[str, object]],
    aula_places: list[dict[str, object]],
    known_building_ids: set[str],
) -> None:
    place_by_id = {
        str(place.get("place_id")): place
        for place in aula_places
        if isinstance(place.get("place_id"), str)
    }

    drop_place_ids: set[str] = set()
    kept_aulas: list[dict[str, object]] = []

    for aula in aulas:
        source_url = str(aula.get("source_url") or "").casefold()
        name = str(aula.get("name") or "")
        lowered_name = name.casefold()

        override_building_id: str | None = None
        override_floor: str | None = None
        override_capacity: int | None = None
        should_drop = False
        existing_building_id = (
            str(aula.get("building_id")).strip()
            if isinstance(aula.get("building_id"), str)
            else None
        )

        # Campus map/department sources often omit explicit floor for capannoni.
        # Domain rule from manual review: capannoni aulas default to ground floor.
        if (
            existing_building_id
            and existing_building_id.startswith("capannone-")
            and existing_building_id in known_building_ids
            and not isinstance(aula.get("floor"), str)
        ):
            override_floor = "Piano Terra"

        if "ctc.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if lowered_name == "aula studio per i soli studenti di chimica":
                override_building_id = "cubo-15c"
                override_floor = "Secondo piano"

        elif "dimes.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if lowered_name == "aula e":
                should_drop = True
            elif lowered_name in {"aula ds5", "aula ds6", "aula ds7", "aula ds8"}:
                override_floor = "Secondo piano"
            elif lowered_name in {"aula p1", "aula p5", "aula p6"}:
                # Dimes page reports these aulas on "Ponte Carrabile".
                override_floor = "Sesto piano"

        elif "dices.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if lowered_name == "aula dolci":
                override_building_id = "cubo-29b"
                override_floor = "Secondo piano"
                override_capacity = 280

        elif "dimeg.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if lowered_name == "aula lime laboratory of innovation and management engineering":
                # Source text references 41C/42C/45C; use 41C as deterministic anchor.
                override_building_id = "cubo-41c"
            elif lowered_name in {"aula p1", "aula p3", "aula p4"}:
                # Dimeg page reports these aulas on "Ponte Carrabile".
                override_floor = "Sesto piano"
            elif lowered_name in {"aula consolidata 43b", "aula b (consolidata)", "aula consolidata b"}:
                # Dimeg page reports consolidated 43B/43C aulas on "Ponte Pedonale".
                override_floor = "Quarto piano"

        elif "dinci.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if "giannattasio" in lowered_name:
                override_building_id = "cubo-45b"
                override_floor = "Primo piano"

        elif "unical.prod.up.cineca.it/calendar/activities/" in source_url:
            if lowered_name in {
                "aula blu",
                "aula verde",
                "laboratorio a",
                "laboratorio b",
                "laboratorio c",
                "spazio mostre",
            }:
                should_drop = True
            elif "multimediale" in lowered_name and "25" in lowered_name:
                override_building_id = "cla-centro-linguistico-d-ateneo"
            elif "giannattasio" in lowered_name and existing_building_id == "cubo-45b":
                override_floor = "Primo piano"
            elif "superiore" in lowered_name:
                override_floor = "Primo piano"
            elif "inferiore" in lowered_name:
                override_floor = "Piano Terra"
        elif "cla.unical.it/servizi-linguistici/studio-in-autonomia/" in source_url:
            if "multimediale cla" in lowered_name:
                override_building_id = "cla-centro-linguistico-d-ateneo"
        elif "diam.unical.it/dipartimento/organizzazione/strutture/" in source_url:
            if "giannattasio" in lowered_name and existing_building_id == "cubo-45b":
                override_floor = "Primo piano"

        if not override_floor and not isinstance(aula.get("floor"), str):
            override_floor = _infer_floor_from_code_hints(
                name=name,
                room=aula.get("room"),
                short_code=aula.get("short_code"),
                building_id=existing_building_id,
            )

        if should_drop:
            place_id = aula.get("place_id")
            if isinstance(place_id, str):
                drop_place_ids.add(place_id)
            continue

        if override_building_id and override_building_id in known_building_ids:
            _set_aula_building_id(
                aula=aula,
                building_id=override_building_id,
                place_by_id=place_by_id,
                force=True,
            )

        if override_floor and not isinstance(aula.get("floor"), str):
            aula["floor"] = override_floor
            place_id = aula.get("place_id")
            if isinstance(place_id, str):
                place = place_by_id.get(place_id)
                if place is not None and not isinstance(place.get("floor"), str):
                    place["floor"] = override_floor

        if override_capacity is not None:
            existing_capacity = aula.get("capacity")
            if not isinstance(existing_capacity, int) or existing_capacity < override_capacity:
                aula["capacity"] = override_capacity

        kept_aulas.append(aula)

    aulas[:] = kept_aulas
    if drop_place_ids:
        aula_places[:] = [
            place
            for place in aula_places
            if not (isinstance(place.get("place_id"), str) and str(place.get("place_id")) in drop_place_ids)
        ]


def _infer_floor_from_code_hints(
    name: str,
    room: object,
    short_code: object,
    building_id: str | None,
) -> str | None:
    values = [name]
    if isinstance(room, str):
        values.append(room)
    if isinstance(short_code, str):
        values.append(short_code)
    joined = " ".join(values)
    lowered = joined.casefold()
    upper = joined.upper()

    if "ponte carrabile" in lowered:
        return "Sesto piano"
    if "ponte pedonale" in lowered:
        return "Quarto piano"

    ch_style = re.search(r"\b(?:[A-Z]{1,4}-)?\d{1,2}-([0-7])[A-Z](?:-\d{1,2}[A-Z])?\b", upper)
    if ch_style:
        return _floor_label_from_digit(int(ch_style.group(1)))

    lab_style = re.search(r"\bLAB\s*\d{1,2}[A-Z][_-]([0-7])P\b", upper)
    if lab_style:
        return _floor_label_from_digit(int(lab_style.group(1)))

    if building_id == "cubo-45b" and re.search(r"\b45B0[0-9A-Z]\b", upper):
        return "Piano Terra"

    cubo_floor_tokens = re.findall(r"\b\d{1,2}[A-Z]\s*([0-7])[A-Z]\d?\b", upper)
    if cubo_floor_tokens:
        digits = {int(token) for token in cubo_floor_tokens}
        if len(digits) == 1:
            return _floor_label_from_digit(digits.pop())

    if building_id:
        building_match = re.fullmatch(r"cubo-([0-9]{1,2})([a-z])", building_id)
        if building_match:
            number = building_match.group(1)
            letter = building_match.group(2).upper()
            prefix = rf"\b{number}\s*{letter}\s*([0-7])(?:[A-Z]\d?)?\b"
            floor_digits = {int(token) for token in re.findall(prefix, upper)}
            if len(floor_digits) == 1:
                return _floor_label_from_digit(floor_digits.pop())

    return None


def _floor_label_from_digit(value: int) -> str:
    labels = {
        0: "Piano Terra",
        1: "Primo piano",
        2: "Secondo piano",
        3: "Terzo piano",
        4: "Quarto piano",
        5: "Quinto piano",
        6: "Sesto piano",
        7: "Settimo piano",
    }
    return labels[value]


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

    for match in re.finditer(r"\bcapannone\s+([a-z])\b", lowered):
        building_id = f"capannone-{match.group(1)}"
        if building_id in known_building_ids:
            candidates.add(building_id)

    if "orto botanico" in lowered and "orto-botanico" in known_building_ids:
        candidates.add("orto-botanico")

    if "polifunzionale" in lowered:
        polifunzionale_ids = sorted(
            building_id
            for building_id in known_building_ids
            if building_id.startswith("polifunzionale")
        )
        if len(polifunzionale_ids) == 1:
            candidates.add(polifunzionale_ids[0])

    if any(token in lowered for token in (" cla ", "centro linguistico", "centro-linguistico")):
        cla_id = "cla-centro-linguistico-d-ateneo"
        if cla_id in known_building_ids:
            candidates.add(cla_id)

    return candidates


def _collapse_duplicate_aulas(
    aulas: list[dict[str, object]],
    aula_places: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for aula in aulas:
        key = _aula_duplicate_key(aula)
        if key is None:
            key = f"__single__{str(aula.get('aula_id') or '')}"
        grouped.setdefault(key, []).append(aula)

    place_by_id = {
        str(place.get("place_id")): dict(place)
        for place in aula_places
        if isinstance(place.get("place_id"), str)
    }

    merged_aulas: list[dict[str, object]] = []
    merged_places_by_id: dict[str, dict[str, object]] = {}

    for key in sorted(grouped):
        group = grouped[key]
        if len(group) == 1:
            aula = dict(group[0])
            merged_aulas.append(aula)
            place_id = aula.get("place_id")
            if isinstance(place_id, str):
                place = place_by_id.get(place_id)
                if place:
                    merged_places_by_id[place_id] = dict(place)
            continue

        merged_aula = _merge_duplicate_aula_group(group)
        merged_aulas.append(merged_aula)

        place_records = [
            dict(place_by_id[place_id])
            for place_id in (
                aula.get("place_id")
                for aula in group
                if isinstance(aula.get("place_id"), str)
            )
            if isinstance(place_id, str) and place_id in place_by_id
        ]

        merged_place = _merge_duplicate_place_group(place_records=place_records, aula=merged_aula)
        merged_places_by_id[str(merged_place["place_id"])] = merged_place

    deduped_aulas = sorted(merged_aulas, key=lambda item: str(item.get("aula_id") or ""))
    deduped_places = sorted(merged_places_by_id.values(), key=lambda item: str(item.get("place_id") or ""))
    return deduped_aulas, deduped_places


def _aula_duplicate_key(aula: dict[str, object]) -> str | None:
    building_id = aula.get("building_id")
    if not isinstance(building_id, str):
        return None

    normalized_name = _normalize_lookup_value(aula.get("normalized_name") or aula.get("name"))
    if not normalized_name:
        return None

    return f"{normalized_name}|{building_id}"


def _merge_duplicate_aula_group(group: list[dict[str, object]]) -> dict[str, object]:
    ordered = sorted(group, key=_aula_merge_rank, reverse=True)
    primary = dict(ordered[0])
    secondary = ordered[1:]

    for field in ("short_code", "room", "floor"):
        if primary.get(field):
            continue
        for item in secondary:
            value = item.get(field)
            if isinstance(value, str) and value:
                primary[field] = value
                break

    capacities = [
        value
        for value in (item.get("capacity") for item in ordered)
        if isinstance(value, int) and value > 0
    ]
    if capacities:
        primary["capacity"] = max(capacities)

    tokens: set[str] = set(
        token
        for token in primary.get("search_tokens", [])
        if isinstance(token, str) and token
    )
    for item in secondary:
        tokens.update(
            token
            for token in item.get("search_tokens", [])
            if isinstance(token, str) and token
        )
    if tokens:
        primary["search_tokens"] = sorted(tokens)

    return primary


def _merge_duplicate_place_group(
    place_records: list[dict[str, object]],
    aula: dict[str, object],
) -> dict[str, object]:
    if not place_records:
        merged: dict[str, object] = {
            "place_id": str(aula.get("place_id") or aula.get("aula_id") or ""),
            "type": "AULA",
            "name": str(aula.get("name") or ""),
            "source_id": str(aula.get("source_id") or "unical-aulas"),
            "source_url": str(aula.get("source_url") or ""),
            "last_verified_at": str(aula.get("last_verified_at") or ""),
        }
        if isinstance(aula.get("building_id"), str):
            merged["building_id"] = aula["building_id"]
        if isinstance(aula.get("floor"), str):
            merged["floor"] = aula["floor"]
        if isinstance(aula.get("room"), str):
            merged["room"] = aula["room"]
        return merged

    ordered_places = sorted(place_records, key=_place_merge_rank, reverse=True)
    primary = dict(ordered_places[0])
    secondary = ordered_places[1:]

    primary["place_id"] = str(aula.get("place_id") or primary.get("place_id") or "")
    primary["type"] = "AULA"
    primary["name"] = str(aula.get("name") or primary.get("name") or "")
    primary["source_id"] = str(aula.get("source_id") or primary.get("source_id") or "unical-aulas")
    primary["source_url"] = str(aula.get("source_url") or primary.get("source_url") or "")
    primary["last_verified_at"] = str(aula.get("last_verified_at") or primary.get("last_verified_at") or "")

    if isinstance(aula.get("building_id"), str):
        primary["building_id"] = aula["building_id"]
    if isinstance(aula.get("floor"), str):
        primary["floor"] = aula["floor"]
    elif not isinstance(primary.get("floor"), str):
        for item in secondary:
            value = item.get("floor")
            if isinstance(value, str) and value:
                primary["floor"] = value
                break
    if isinstance(aula.get("room"), str):
        primary["room"] = aula["room"]
    elif not isinstance(primary.get("room"), str):
        for item in secondary:
            value = item.get("room")
            if isinstance(value, str) and value:
                primary["room"] = value
                break

    if not (isinstance(primary.get("lat"), (int, float)) and isinstance(primary.get("lng"), (int, float))):
        for item in secondary:
            lat = item.get("lat")
            lng = item.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                primary["lat"] = lat
                primary["lng"] = lng
                break

    return primary


def _aula_merge_rank(aula: dict[str, object]) -> tuple[int, int, int, int, int, int, str]:
    source_url = str(aula.get("source_url") or "").casefold()
    name = str(aula.get("name") or "")
    aula_id = str(aula.get("aula_id") or "")
    building_id = str(aula.get("building_id") or "")
    return (
        1 if aula.get("floor") else 0,
        1 if isinstance(aula.get("capacity"), int) else 0,
        1 if aula.get("short_code") else 0,
        1 if aula.get("room") else 0,
        1 if "calendar/activities" not in source_url else 0,
        1 if building_id and building_id in aula_id else 0,
        1 if any(char.islower() for char in name) else 0,
    )


def _place_merge_rank(place: dict[str, object]) -> tuple[int, int, int, int]:
    source_url = str(place.get("source_url") or "").casefold()
    return (
        1 if isinstance(place.get("lat"), (int, float)) and isinstance(place.get("lng"), (int, float)) else 0,
        1 if place.get("floor") else 0,
        1 if place.get("room") else 0,
        1 if "calendar/activities" not in source_url else 0,
    )


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
