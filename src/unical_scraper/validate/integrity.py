"""Referential integrity checks for normalized datasets."""

from __future__ import annotations

import json
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
    """Run MVP referential checks across people/departments/places."""
    departments = _load_array(data_dir / "departments.json")
    places = _load_array(data_dir / "places.json")
    people = _load_array(data_dir / "people.json")

    department_ids = {item.get("department_id") for item in departments if item.get("department_id")}
    place_ids = {item.get("place_id") for item in places if item.get("place_id")}
    place_types = {
        item.get("place_id"): item.get("type")
        for item in places
        if item.get("place_id")
    }

    issues: list[IntegrityIssue] = []
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
