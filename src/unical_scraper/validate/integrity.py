"""Referential integrity checks for normalized datasets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IntegrityIssue:
    """Single integrity issue found across datasets."""

    level: str
    file: str
    message: str
    record_id: str | None = None


def _load_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def check_integrity(data_dir: Path) -> list[IntegrityIssue]:
    """Run referential checks across people/departments/places/aulas/aliases."""
    buildings = _load_array(data_dir / "buildings.json")
    departments = _load_array(data_dir / "departments.json")
    places = _load_array(data_dir / "places.json")
    people = _load_array(data_dir / "people.json")
    aulas = _load_array(data_dir / "aulas.json")
    aliases = _load_array(data_dir / "aliases.json")

    building_ids = {item.get("building_id") for item in buildings if item.get("building_id")}
    department_ids = {item.get("department_id") for item in departments if item.get("department_id")}
    place_ids = {item.get("place_id") for item in places if item.get("place_id")}
    place_types = {
        item.get("place_id"): item.get("type")
        for item in places
        if item.get("place_id")
    }
    place_buildings = {
        item.get("place_id"): item.get("building_id")
        for item in places
        if item.get("place_id")
    }
    person_ids = {item.get("person_id") for item in people if item.get("person_id")}

    issues: list[IntegrityIssue] = []
    for department in departments:
        department_id = department.get("department_id")
        primary_building_id = department.get("primary_building_id")
        if primary_building_id and primary_building_id not in building_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="departments.json",
                    record_id=str(department_id) if department_id else None,
                    message=f"primary_building_id '{primary_building_id}' does not exist in buildings.json",
                )
            )

    for place in places:
        place_id = place.get("place_id")
        building_id = place.get("building_id")
        if building_id and building_id not in building_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="places.json",
                    record_id=str(place_id) if place_id else None,
                    message=f"building_id '{building_id}' does not exist in buildings.json",
                )
            )

    for person in people:
        person_id = person.get("person_id")

        department_id = person.get("department_id")
        if department_id and department_id not in department_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="people.json",
                    record_id=str(person_id) if person_id else None,
                    message=f"department_id '{department_id}' does not exist in departments.json",
                )
            )

        office_place_id = person.get("office_place_id")
        if office_place_id and office_place_id not in place_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="people.json",
                    record_id=str(person_id) if person_id else None,
                    message=f"office_place_id '{office_place_id}' does not exist in places.json",
                )
            )
            continue

        if office_place_id and place_types.get(office_place_id) != "OFFICE":
            issues.append(
                IntegrityIssue(
                    level="warning",
                    file="people.json",
                    record_id=str(person_id) if person_id else None,
                    message=f"office_place_id '{office_place_id}' points to a non-OFFICE place",
                )
            )

    for aula in aulas:
        aula_id = aula.get("aula_id")
        place_id = aula.get("place_id")
        if place_id and place_id not in place_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="aulas.json",
                    record_id=str(aula_id) if aula_id else None,
                    message=f"place_id '{place_id}' does not exist in places.json",
                )
            )
            continue

        if place_id and place_types.get(place_id) != "AULA":
            issues.append(
                IntegrityIssue(
                    level="warning",
                    file="aulas.json",
                    record_id=str(aula_id) if aula_id else None,
                    message=f"place_id '{place_id}' points to a non-AULA place",
                )
            )

        building_id = aula.get("building_id")
        if building_id and building_id not in building_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="aulas.json",
                    record_id=str(aula_id) if aula_id else None,
                    message=f"building_id '{building_id}' does not exist in buildings.json",
                )
            )

        if place_id and building_id and place_buildings.get(place_id) and building_id != place_buildings.get(place_id):
            issues.append(
                IntegrityIssue(
                    level="warning",
                    file="aulas.json",
                    record_id=str(aula_id) if aula_id else None,
                    message=(
                        f"building_id '{building_id}' differs from places.json building_id "
                        f"'{place_buildings.get(place_id)}' for place_id '{place_id}'"
                    ),
                )
            )

        department_id = aula.get("department_id")
        if department_id and department_id not in department_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="aulas.json",
                    record_id=str(aula_id) if aula_id else None,
                    message=f"department_id '{department_id}' does not exist in departments.json",
                )
            )

    seen_aula_keys: dict[tuple[str, str], str] = {}
    for aula in aulas:
        aula_id = str(aula.get("aula_id") or "")
        building_id = aula.get("building_id")
        if not isinstance(building_id, str):
            continue

        normalized_name = str(aula.get("normalized_name") or aula.get("name") or "")
        normalized_name = " ".join(normalized_name.split()).casefold()
        if not normalized_name:
            continue

        key = (normalized_name, building_id)
        previous_aula_id = seen_aula_keys.get(key)
        if previous_aula_id and previous_aula_id != aula_id:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="aulas.json",
                    record_id=aula_id or None,
                    message=(
                        "duplicate aula key for "
                        f"normalized_name '{normalized_name}' and building_id '{building_id}' "
                        f"(also in '{previous_aula_id}')"
                    ),
                )
            )
            continue
        seen_aula_keys[key] = aula_id

    room_floor_by_key: dict[tuple[str, str], dict[str, set[str]]] = {}
    for aula in aulas:
        aula_id = str(aula.get("aula_id") or "")
        building_id = aula.get("building_id")
        room = aula.get("room")
        floor = aula.get("floor")
        if not isinstance(building_id, str) or not building_id.strip():
            continue
        if not isinstance(room, str) or not room.strip():
            continue
        if not isinstance(floor, str) or not floor.strip():
            continue

        key = (building_id.strip(), " ".join(room.split()).casefold())
        floor_label = " ".join(floor.split())
        room_floor_by_key.setdefault(key, {}).setdefault(floor_label, set()).add(aula_id)

    for (building_id, room_key), floors_map in sorted(room_floor_by_key.items()):
        if len(floors_map) <= 1:
            continue
        floor_labels = sorted(floors_map.keys())
        aula_ids = sorted(aula_id for ids in floors_map.values() for aula_id in ids if aula_id)
        issues.append(
            IntegrityIssue(
                level="error",
                file="aulas.json",
                record_id=aula_ids[0] if aula_ids else None,
                message=(
                    f"conflicting floor for room '{room_key}' in building_id '{building_id}': "
                    f"{', '.join(floor_labels)}"
                ),
            )
        )

    seen_near_duplicate_keys: dict[tuple[str, tuple[str, ...]], set[str]] = {}
    for aula in aulas:
        aula_id = str(aula.get("aula_id") or "")
        building_id = aula.get("building_id")
        if not isinstance(building_id, str) or not building_id.strip():
            continue

        raw_name = str(aula.get("normalized_name") or aula.get("name") or "")
        tokens = _aula_token_set(raw_name)
        if len(tokens) < 2:
            continue

        key = (building_id.strip(), tokens)
        seen_near_duplicate_keys.setdefault(key, set()).add(aula_id)

    for (building_id, tokens), aula_ids in sorted(seen_near_duplicate_keys.items()):
        if len(aula_ids) <= 1:
            continue
        sorted_ids = sorted(aula_id for aula_id in aula_ids if aula_id)
        issues.append(
            IntegrityIssue(
                level="warning",
                file="aulas.json",
                record_id=sorted_ids[0] if sorted_ids else None,
                message=(
                    "suspicious near-duplicate aulas for "
                    f"building_id '{building_id}' and token_set '{' '.join(tokens)}': "
                    f"{', '.join(sorted_ids)}"
                ),
            )
        )

    alias_targets = {
        "BUILDING": building_ids,
        "PLACE": place_ids,
        "PERSON": person_ids,
        "DEPARTMENT": department_ids,
    }
    for alias in aliases:
        alias_id = alias.get("alias_id")
        entity_type = alias.get("entity_type")
        entity_id = alias.get("entity_id")
        if not isinstance(entity_type, str) or not entity_id:
            continue

        target_ids = alias_targets.get(entity_type)
        if target_ids is None:
            continue

        if entity_id not in target_ids:
            issues.append(
                IntegrityIssue(
                    level="error",
                    file="aliases.json",
                    record_id=str(alias_id) if alias_id else None,
                    message=f"entity_id '{entity_id}' does not exist for entity_type '{entity_type}'",
                )
            )

    return sorted(issues, key=lambda issue: (issue.level, issue.file, issue.record_id or "", issue.message))


def issues_to_dicts(issues: list[IntegrityIssue]) -> list[dict[str, str]]:
    """Convert issues to JSON-serializable dictionaries."""
    return [
        {
            "level": issue.level,
            "file": issue.file,
            "message": issue.message,
            **({"record_id": issue.record_id} if issue.record_id else {}),
        }
        for issue in issues
    ]


def _aula_token_set(value: str) -> tuple[str, ...]:
    cleaned = value.casefold()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    tokens = {
        token
        for token in cleaned.split()
        if token and token not in {"aula", "laboratorio", "lab"}
    }
    return tuple(sorted(tokens))
