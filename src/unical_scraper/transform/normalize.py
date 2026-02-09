"""Normalization layer from raw extraction to canonical JSON entities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..extract.departments import RawDepartment
from ..extract.teachers import RawTeacher
from ..utils.text import collapse_whitespace, none_if_empty
from .dedupe import dedupe_people
from .ids import make_department_id, make_person_id


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


def write_json(path: Path, payload: object) -> None:
    """Write deterministic JSON files for PR-friendly diffs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")
