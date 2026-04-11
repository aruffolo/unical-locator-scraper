"""Grouped service-location contract helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.text import collapse_whitespace, none_if_empty


def load_service_location_contract(path: Path) -> dict[str, Any]:
    """Load deterministic grouped-location supplement data."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("service location contract must be a JSON object")
    return payload


def apply_service_location_contract(
    *,
    places: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
    contract: dict[str, Any],
    verified_at: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply first-wave grouped service-location modeling."""
    if verified_at is None:
        verified_at = datetime.now(timezone.utc)

    verified_iso = verified_at.isoformat()
    places_by_id = {
        str(item["place_id"]): dict(item)
        for item in places
        if isinstance(item, dict) and isinstance(item.get("place_id"), str)
    }
    buildings_by_id = {
        str(item["building_id"]): dict(item)
        for item in buildings
        if isinstance(item, dict) and isinstance(item.get("building_id"), str)
    }

    for place_id in _string_list(contract.get("clear_overview_building_ids")):
        place = places_by_id.get(place_id)
        if place is None:
            continue
        place.pop("building_id", None)
        place["last_verified_at"] = verified_iso

    for spec in _object_list(contract.get("quartieri_places")):
        place_id = _required_string(spec, "place_id")
        merged = dict(places_by_id.get(place_id, {}))
        merged.update(
            {
                "place_id": place_id,
                "type": _required_string(spec, "type"),
                "name": _required_string(spec, "name"),
                "lat": _required_number(spec, "lat"),
                "lng": _required_number(spec, "lng"),
                "source_id": _required_string(spec, "source_id"),
                "source_url": _required_string(spec, "source_url"),
                "last_verified_at": verified_iso,
            }
        )
        merged.pop("building_id", None)
        _merge_optional_place_fields(merged, spec)
        places_by_id[place_id] = merged

    for spec in _object_list(contract.get("mensa_buildings")):
        building_id = _required_string(spec, "building_id")
        merged = dict(buildings_by_id.get(building_id, {}))
        merged["building_id"] = building_id
        merged["name"] = _required_string(spec, "name")
        merged["category"] = _required_string(spec, "category")
        merged["last_verified_at"] = verified_iso

        lat = spec.get("lat")
        lng = spec.get("lng")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            merged["lat"] = round(float(lat), 7)
            merged["lng"] = round(float(lng), 7)

        source_id = _optional_string(spec, "source_id")
        source_url = _optional_string(spec, "source_url")
        if source_id:
            merged["source_id"] = source_id
        if source_url:
            merged["source_url"] = source_url

        buildings_by_id[building_id] = merged

    for building_id in _string_list(contract.get("remove_building_ids")):
        buildings_by_id.pop(building_id, None)

    entity_links = [
        _normalize_entity_link(spec)
        for spec in _object_list(contract.get("entity_links"))
    ]

    return (
        sorted(places_by_id.values(), key=lambda item: str(item.get("place_id", ""))),
        sorted(buildings_by_id.values(), key=lambda item: str(item.get("building_id", ""))),
        sorted(entity_links, key=lambda item: item["link_id"]),
    )


def _normalize_entity_link(spec: dict[str, Any]) -> dict[str, Any]:
    parent_entity_id = _required_string(spec, "parent_entity_id")
    relation_type = _required_string(spec, "relation_type")
    child_entity_id = _required_string(spec, "child_entity_id")

    link: dict[str, Any] = {
        "link_id": f"{parent_entity_id}__{relation_type.casefold()}__{child_entity_id}",
        "parent_entity_type": _required_string(spec, "parent_entity_type"),
        "parent_entity_id": parent_entity_id,
        "relation_type": relation_type,
        "child_entity_type": _required_string(spec, "child_entity_type"),
        "child_entity_id": child_entity_id,
    }

    sort_order = spec.get("sort_order")
    if isinstance(sort_order, int):
        link["sort_order"] = sort_order

    source_id = _optional_string(spec, "source_id")
    source_url = _optional_string(spec, "source_url")
    if source_id:
        link["source_id"] = source_id
    if source_url:
        link["source_url"] = source_url

    return link


def _merge_optional_place_fields(
    place: dict[str, Any],
    spec: dict[str, Any],
) -> None:
    for field in [
        "description",
        "email",
        "phone",
        "website_url",
        "opening_hours",
        "access_notes",
    ]:
        value = _optional_string(spec, field)
        if value:
            place[field] = value


def _object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = _optional_string(payload, key)
    if value is None:
        raise ValueError(f"missing required string field: {key}")
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    return none_if_empty(collapse_whitespace(value))


def _required_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"missing required numeric field: {key}")
    return round(float(value), 7)
