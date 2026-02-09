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
    """Build a compact report with validation status and people coverage."""
    people = _load_array(data_dir / "people.json")
    total_people = len(people)

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
