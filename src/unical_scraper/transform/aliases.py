"""Alias generation helpers for robust end-user search recall."""

from __future__ import annotations

import re
from typing import Any

from ..utils.text import collapse_whitespace, none_if_empty, slugify
from .ids import stable_slug


_AULA_PREFIX_RE = re.compile(r"^aula\s+", flags=re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"[\s\-_./]+")
_LANDMARK_ALIAS_TARGETS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "BUILDING",
        "teatro-piccolo",
        ("PTU", "PTU Piccolo Teatro Unical", "Piccolo Teatro Unical"),
    ),
    (
        "PLACE",
        "service-centro-congressi",
        (
            "Centro Congressi",
            "Centro Congressi Aula Magna B. Andreatta",
            "Aula Magna B. Andreatta",
        ),
    ),
    (
        "BUILDING",
        "aula-magna",
        ("Aula Magna B. Andreatta",),
    ),
    (
        "PLACE",
        "service-biblioteche",
        ("Biblioteche", "Biblioteca", "Biblioteca di Ateneo"),
    ),
    (
        "BUILDING",
        "cla-centro-linguistico-d-ateneo",
        ("CLA 25C - 17A", "CLA 25C", "CLA 17A", "Centro Linguistico d'Ateneo"),
    ),
    (
        "BUILDING",
        "cubo-25b",
        ("Rettorato", "Direzione Generale"),
    ),
    (
        "BUILDING",
        "cappella-universitaria",
        ("Cappella", "Cappella Universitaria", "Cappella 24B"),
    ),
    (
        "BUILDING",
        "cubo-24b",
        ("University Club",),
    ),
    (
        "PLACE",
        "service-centro-sanitario",
        ("Centro Sanitario 34B", "Guardia Medica"),
    ),
    (
        "BUILDING",
        "auditorium-teatro-grande",
        ("TAU", "TAU Teatro Auditorium Unical Cinema Campus", "Cinema Campus"),
    ),
    (
        "PLACE",
        "service-polo-infanzia",
        (
            "Polo Infanzia",
            "Ufficio postale",
            "Ufficio postale Polo Infanzia",
            "Liaison Office - Technest",
        ),
    ),
    (
        "BUILDING",
        "centro-radiotelevisivo",
        ("Aula U. Caldora",),
    ),
    (
        "BUILDING",
        "mensa-martenson",
        ("Mensa Martenson", "Mensa Quartiere Martenson"),
    ),
)


def build_aula_place_aliases(
    aulas: list[dict[str, Any]],
    places: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Create deterministic aliases for AULA places from `aulas.json` fields."""
    aula_place_ids = {
        str(place.get("place_id"))
        for place in places
        if place.get("type") == "AULA" and isinstance(place.get("place_id"), str)
    }

    aliases_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for aula in sorted(aulas, key=lambda item: str(item.get("place_id", ""))):
        place_id = _clean_str(aula.get("place_id"))
        if not place_id or place_id not in aula_place_ids:
            continue

        for label in _collect_aula_alias_labels(aula):
            normalized = slugify(label)
            if not normalized:
                continue

            key = ("PLACE", place_id, normalized)
            aliases_by_key.setdefault(
                key,
                {
                    "alias_id": stable_slug(f"alias-place-{place_id}-{normalized}"),
                    "entity_type": "PLACE",
                    "entity_id": place_id,
                    "label": label,
                    "normalized": normalized,
                },
            )

    return sorted(aliases_by_key.values(), key=lambda item: item["alias_id"])


def build_landmark_aliases(
    buildings: list[dict[str, Any]],
    places: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Create deterministic aliases for map/PDF landmark labels."""
    place_ids = {
        str(place.get("place_id"))
        for place in places
        if isinstance(place.get("place_id"), str)
    }
    building_ids = {
        str(building.get("building_id"))
        for building in buildings
        if isinstance(building.get("building_id"), str)
    }

    aliases_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for entity_type, entity_id, labels in _LANDMARK_ALIAS_TARGETS:
        target_ids = building_ids if entity_type == "BUILDING" else place_ids
        if entity_id not in target_ids:
            continue
        for label in labels:
            _register_alias(
                aliases_by_key=aliases_by_key,
                entity_type=entity_type,
                entity_id=entity_id,
                label=label,
            )

    return sorted(aliases_by_key.values(), key=lambda item: item["alias_id"])


def build_search_aliases(
    aulas: list[dict[str, Any]],
    places: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Combine aula and landmark aliases in a single deterministic dataset."""
    aliases_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for alias in build_aula_place_aliases(aulas=aulas, places=places):
        _register_alias(
            aliases_by_key=aliases_by_key,
            entity_type="PLACE",
            entity_id=alias.get("entity_id"),
            label=alias.get("label"),
        )

    for alias in build_landmark_aliases(buildings=buildings, places=places):
        _register_alias(
            aliases_by_key=aliases_by_key,
            entity_type=alias.get("entity_type"),
            entity_id=alias.get("entity_id"),
            label=alias.get("label"),
        )

    return sorted(aliases_by_key.values(), key=lambda item: item["alias_id"])


def _collect_aula_alias_labels(aula: dict[str, Any]) -> list[str]:
    ordered_labels: list[str] = []
    seen: set[str] = set()

    name = _clean_str(aula.get("name"))
    room = _clean_str(aula.get("room"))
    short_code = _normalize_code(aula.get("short_code"))

    if name:
        _append_unique_label(ordered_labels, seen, name)
        if _starts_with_aula(name):
            no_prefix = _remove_aula_prefix(name)
            if no_prefix:
                _append_unique_label(ordered_labels, seen, no_prefix)

    if room:
        _append_unique_label(ordered_labels, seen, room)
        compact_room = _normalize_code(room)
        if compact_room and compact_room != room.upper():
            _append_unique_label(ordered_labels, seen, compact_room)
        for variant in _split_alnum_boundaries(_normalize_code(room) or ""):
            _append_unique_label(ordered_labels, seen, variant)
        if _looks_like_room_code(room) and not _starts_with_aula(room):
            _append_unique_label(ordered_labels, seen, f"Aula {room}")

    if short_code:
        _append_unique_label(ordered_labels, seen, short_code)
        _append_unique_label(ordered_labels, seen, f"Aula {short_code}")
        for variant in _split_alnum_boundaries(short_code):
            _append_unique_label(ordered_labels, seen, variant)
            _append_unique_label(ordered_labels, seen, f"Aula {variant}")

    if name and _looks_like_room_code(name) and not _starts_with_aula(name):
        _append_unique_label(ordered_labels, seen, f"Aula {name}")

    return ordered_labels


def _append_unique_label(target: list[str], seen: set[str], label: str) -> None:
    cleaned = none_if_empty(collapse_whitespace(label))
    if not cleaned:
        return
    key = cleaned.casefold()
    if key in seen:
        return
    seen.add(key)
    target.append(cleaned)


def _register_alias(
    aliases_by_key: dict[tuple[str, str, str], dict[str, str]],
    entity_type: Any,
    entity_id: Any,
    label: Any,
) -> None:
    if not isinstance(entity_type, str) or entity_type not in {"BUILDING", "PLACE"}:
        return
    if not isinstance(entity_id, str):
        return
    cleaned_label = _clean_str(label)
    if not cleaned_label:
        return
    normalized = slugify(cleaned_label)
    if not normalized:
        return

    key = (entity_type, entity_id, normalized)
    aliases_by_key.setdefault(
        key,
        {
            "alias_id": stable_slug(f"alias-{entity_type.casefold()}-{entity_id}-{normalized}"),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "label": cleaned_label,
            "normalized": normalized,
        },
    )


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return none_if_empty(collapse_whitespace(value))


def _starts_with_aula(value: str) -> bool:
    return bool(_AULA_PREFIX_RE.match(value))


def _remove_aula_prefix(value: str) -> str | None:
    stripped = _AULA_PREFIX_RE.sub("", value, count=1)
    return none_if_empty(collapse_whitespace(stripped))


def _normalize_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    compact = _SEPARATOR_RE.sub("", value).strip().upper()
    return compact if compact else None


def _split_alnum_boundaries(code: str) -> list[str]:
    if not code or not code.isalnum():
        return []
    chunks: list[str] = []
    current = [code[0]]
    for char in code[1:]:
        if char.isalpha() == current[-1].isalpha():
            current.append(char)
        else:
            chunks.append("".join(current))
            current = [char]
    chunks.append("".join(current))
    if len(chunks) <= 1:
        return []
    return [" ".join(chunks)]


def _looks_like_room_code(value: str) -> bool:
    compact = _normalize_code(value)
    if not compact:
        return False
    if len(compact) > 12:
        return False
    patterns = (
        r"[A-Z]{1,5}\d{1,4}[A-Z]?",
        r"\d{1,3}[A-Z]{1,4}\d{0,3}[A-Z]?",
        r"[A-Z]\d{1,3}",
    )
    return any(re.fullmatch(pattern, compact) for pattern in patterns)
