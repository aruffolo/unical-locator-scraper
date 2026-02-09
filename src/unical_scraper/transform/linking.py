"""Deterministic linking helpers across normalized datasets."""

from __future__ import annotations

import re
from typing import Any


_CUBO_RE = re.compile(r"\bcubo\s*([0-9]{1,2}[a-z]?)\b", re.IGNORECASE)


def link_places_to_buildings(
    places: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return places with `building_id` inferred from known building records."""
    building_ids = {
        str(item["building_id"])
        for item in buildings
        if isinstance(item, dict) and item.get("building_id")
    }

    linked: list[dict[str, Any]] = []
    for place in places:
        updated = dict(place)

        existing_building_id = updated.get("building_id")
        if isinstance(existing_building_id, str) and existing_building_id in building_ids:
            linked.append(updated)
            continue

        inferred = _infer_building_id(updated, building_ids)
        if inferred:
            updated["building_id"] = inferred

        linked.append(updated)

    return linked


def _infer_building_id(place: dict[str, Any], known_building_ids: set[str]) -> str | None:
    parts = [
        str(place.get("name") or ""),
        str(place.get("description") or ""),
        str(place.get("source_url") or ""),
        str(place.get("access_notes") or ""),
    ]
    text = " ".join(parts)
    lowered = text.casefold()

    cubo_match = _CUBO_RE.search(lowered)
    if cubo_match:
        cubo_id = f"cubo-{cubo_match.group(1).lower()}"
        if cubo_id in known_building_ids:
            return cubo_id

    if any(token in lowered for token in ["centro-sanitario", "assistenza sanitaria"]):
        if "centro-sanitario" in known_building_ids:
            return "centro-sanitario"

    if any(
        token in lowered
        for token in ["front-office-on-line-cr", "serv-cr", "segnalazioni-e-richieste-cr", "centro residenziale"]
    ):
        target = "uffici-centro-residenziale-e-area-didattica"
        if target in known_building_ids:
            return target

    return None
