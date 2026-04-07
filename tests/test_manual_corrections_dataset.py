from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "normalized"

LOCKED_MIN_COUNTS = {
    "aliases.json": 1374,
    "aulas.json": 517,
    "building_entrances.json": 0,
    "buildings.json": 151,
    "departments.json": 14,
    "faqs.json": 0,
    "glossary.json": 0,
    "people.json": 4156,
    "places.json": 880,
    "sources.json": 5,
}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_dataset(name: str) -> list[dict[str, Any]]:
    payload = _load_json(DATA_DIR / name)
    assert isinstance(payload, list)
    return [entry for entry in payload if isinstance(entry, dict)]


def _by_id(rows: list[dict[str, Any]], id_field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_id = row.get(id_field)
        if isinstance(raw_id, str) and raw_id:
            result[raw_id] = row
    return result


def test_required_entities_are_present_in_canonical_datasets() -> None:
    buildings = _by_id(_load_dataset("buildings.json"), "building_id")
    places = _by_id(_load_dataset("places.json"), "place_id")
    people = _by_id(_load_dataset("people.json"), "person_id")

    assert "cappella-universitaria" in buildings
    assert "cubo-20" in buildings
    assert "office-ufficio-cubo-0-c-primo-piano" in places
    assert "service-centro-sportivo" in places
    assert "office-ufficio-cubo-4c-piano-3" in places
    assert "francesco-scarcello" in people


def test_known_manual_wave_fixes_are_preserved() -> None:
    buildings = _by_id(_load_dataset("buildings.json"), "building_id")
    places = _by_id(_load_dataset("places.json"), "place_id")
    people = _by_id(_load_dataset("people.json"), "person_id")

    cappella = buildings["cappella-universitaria"]
    # Wave 01 safe-drop family: map boilerplate removed from building description.
    assert cappella.get("description") is None

    cubo_20 = buildings["cubo-20"]
    assert cubo_20.get("description") == "Dipartimento di Lingue e Scienze dell'Educazione"
    assert "Link portale:" not in str(cubo_20.get("description"))

    office_0c = places["office-ufficio-cubo-0-c-primo-piano"]
    assert office_0c.get("office_reference_text") == "Cubo 0/C Primo piano"
    assert "Office references:" not in str(office_0c.get("description"))

    service_cus = places["service-centro-sportivo"]
    assert service_cus.get("website_url") == "https://my.unical.it/"
    assert service_cus.get("access_notes") is None

    office_4c = places["office-ufficio-cubo-4c-piano-3"]
    assert isinstance(office_4c.get("meeting_url"), str)
    assert office_4c.get("meeting_code") == "6wlha6g"
    assert "teams.microsoft.com" not in str(office_4c.get("opening_hours")).casefold()

    scarcello = people["francesco-scarcello"]
    assert scarcello.get("office_reference_text") == "Cubo 41C Piano 3"
    assert "Office references:" not in str(scarcello.get("notes"))


def test_dataset_contract_counts_match_files_and_locked_minimums() -> None:
    contract = _load_json(DATA_DIR / "dataset_contract.json")
    assert isinstance(contract, dict)
    datasets = contract.get("datasets")
    assert isinstance(datasets, list)

    contract_counts: dict[str, int] = {}
    for row in datasets:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        records = row.get("records")
        if isinstance(name, str) and isinstance(records, int):
            contract_counts[name] = records

    assert contract_counts.keys() >= LOCKED_MIN_COUNTS.keys()

    for dataset_name, minimum_count in LOCKED_MIN_COUNTS.items():
        dataset_rows = _load_dataset(dataset_name)
        actual_count = len(dataset_rows)
        assert actual_count >= minimum_count
        assert contract_counts[dataset_name] == actual_count

