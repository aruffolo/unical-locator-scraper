"""Coverage report generation helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def build_coverage_report(
    data_dir: Path,
    schema_results: dict[str, list[str]],
    integrity_issues: list[dict[str, str]],
) -> dict[str, Any]:
    """Build a compact report with validation status and dataset coverage."""
    buildings = _load_array(data_dir / "buildings.json")
    departments = _load_array(data_dir / "departments.json")
    places = _load_array(data_dir / "places.json")
    aulas = _load_array(data_dir / "aulas.json")
    people = _load_array(data_dir / "people.json")

    total_buildings = len(buildings)
    total_departments = len(departments)
    total_places = len(places)
    total_aulas = len(aulas)
    total_people = len(people)

    buildings_with_coordinates = sum(
        1 for building in buildings if building.get("lat") is not None and building.get("lng") is not None
    )
    departments_with_email = sum(1 for department in departments if department.get("email"))
    departments_with_website = sum(1 for department in departments if department.get("website_url"))
    departments_with_primary_building = sum(1 for department in departments if department.get("primary_building_id"))
    places_with_building = sum(1 for place in places if place.get("building_id"))
    places_type_aula = sum(1 for place in places if place.get("type") == "AULA")
    aulas_with_place = sum(1 for aula in aulas if aula.get("place_id"))
    aulas_with_building = sum(1 for aula in aulas if aula.get("building_id"))
    aulas_with_floor = sum(1 for aula in aulas if aula.get("floor"))
    aulas_with_short_code = sum(1 for aula in aulas if aula.get("short_code"))
    aulas_with_capacity = sum(1 for aula in aulas if aula.get("capacity") is not None)
    aulas_missing_building = sorted(
        (aula for aula in aulas if not aula.get("building_id")),
        key=lambda aula: str(aula.get("aula_id") or aula.get("name") or ""),
    )
    missing_building_by_source: dict[str, int] = {}
    for aula in aulas_missing_building:
        source_url = str(aula.get("source_url") or "unknown")
        missing_building_by_source[source_url] = missing_building_by_source.get(source_url, 0) + 1
    missing_building_examples = [
        {
            "aula_id": str(aula.get("aula_id") or ""),
            "name": str(aula.get("name") or ""),
            "source_url": str(aula.get("source_url") or ""),
        }
        for aula in aulas_missing_building[:20]
    ]

    with_email = sum(1 for person in people if person.get("email"))
    with_department = sum(1 for person in people if person.get("department_id"))
    with_office_place = sum(1 for person in people if person.get("office_place_id"))
    with_office_hours = sum(1 for person in people if person.get("office_hours"))

    invalid_datasets = {
        dataset: errors for dataset, errors in schema_results.items() if errors
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_datasets": len(schema_results),
            "invalid_datasets": len(invalid_datasets),
            "integrity_issues": len(integrity_issues),
        },
        "schema_validation": {
            "datasets": schema_results,
        },
        "integrity": {
            "issues": integrity_issues,
        },
        "coverage": {
            "buildings": {
                "total": total_buildings,
                "with_coordinates": buildings_with_coordinates,
                "with_coordinates_ratio": _ratio(buildings_with_coordinates, total_buildings),
            },
            "departments": {
                "total": total_departments,
                "with_email": departments_with_email,
                "with_email_ratio": _ratio(departments_with_email, total_departments),
                "with_website_url": departments_with_website,
                "with_website_url_ratio": _ratio(departments_with_website, total_departments),
                "with_primary_building_id": departments_with_primary_building,
                "with_primary_building_id_ratio": _ratio(departments_with_primary_building, total_departments),
            },
            "places": {
                "total": total_places,
                "with_building_id": places_with_building,
                "with_building_id_ratio": _ratio(places_with_building, total_places),
                "type_aula": places_type_aula,
                "type_aula_ratio": _ratio(places_type_aula, total_places),
            },
            "aulas": {
                "total": total_aulas,
                "with_place_id": aulas_with_place,
                "with_place_id_ratio": _ratio(aulas_with_place, total_aulas),
                "with_building_id": aulas_with_building,
                "with_building_id_ratio": _ratio(aulas_with_building, total_aulas),
                "missing_building_id": len(aulas_missing_building),
                "missing_building_id_ratio": _ratio(len(aulas_missing_building), total_aulas),
                "with_floor": aulas_with_floor,
                "with_floor_ratio": _ratio(aulas_with_floor, total_aulas),
                "with_short_code": aulas_with_short_code,
                "with_short_code_ratio": _ratio(aulas_with_short_code, total_aulas),
                "with_capacity": aulas_with_capacity,
                "with_capacity_ratio": _ratio(aulas_with_capacity, total_aulas),
                "missing_building_by_source": [
                    {"source_url": source_url, "count": count}
                    for source_url, count in sorted(
                        missing_building_by_source.items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                ],
                "missing_building_examples": missing_building_examples,
            },
            "people": {
                "total": total_people,
                "with_email": with_email,
                "with_email_ratio": _ratio(with_email, total_people),
                "with_department_id": with_department,
                "with_department_id_ratio": _ratio(with_department, total_people),
                "with_office_place_id": with_office_place,
                "with_office_place_id_ratio": _ratio(with_office_place, total_people),
                "with_office_hours": with_office_hours,
                "with_office_hours_ratio": _ratio(with_office_hours, total_people),
            }
        },
    }
