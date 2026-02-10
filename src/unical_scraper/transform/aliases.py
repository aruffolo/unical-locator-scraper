"""Alias generation helpers for robust end-user search recall."""

from __future__ import annotations

import re
from typing import Any

from ..utils.text import collapse_whitespace, none_if_empty, slugify
from .ids import stable_slug


_AULA_PREFIX_RE = re.compile(r"^aula\s+", flags=re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"[\s\-_./]+")


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
