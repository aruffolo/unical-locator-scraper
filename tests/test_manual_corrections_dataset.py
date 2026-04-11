from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "normalized"

LOCKED_MIN_COUNTS = {
    "aliases.json": 1383,
    "aulas.json": 517,
    "building_entrances.json": 0,
    "buildings.json": 147,
    "departments.json": 14,
    "entity_links.json": 15,
    "faqs.json": 0,
    "glossary.json": 0,
    "people.json": 4156,
    "places.json": 890,
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
    entity_links = _by_id(_load_dataset("entity_links.json"), "link_id")

    assert "cappella-universitaria" in buildings
    assert "cubo-20" in buildings
    assert "mensa-piazza-vermicelli" in buildings
    assert "poli-bistrot-polifunzionale" in buildings
    assert "office-ufficio-cubo-0-c-primo-piano" in places
    assert "service-centro-sportivo" in places
    assert "service-quartieri" in places
    assert "service-servizio-mensa" in places
    assert "quartiere-chiodo" in places
    assert "quartiere-san-gennaro" in places
    assert "office-ufficio-cubo-4c-piano-3" in places
    assert "francesco-scarcello" in people
    assert (
        "service-quartieri__has_child_place__quartiere-chiodo" in entity_links
    )
    assert (
        "service-servizio-mensa__has_child_building__mensa-piazza-vermicelli"
        in entity_links
    )


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


def test_grouped_service_location_wave_is_preserved() -> None:
    buildings = _by_id(_load_dataset("buildings.json"), "building_id")
    places = _by_id(_load_dataset("places.json"), "place_id")
    entity_links = _by_id(_load_dataset("entity_links.json"), "link_id")

    quartieri = places["service-quartieri"]
    assert quartieri.get("building_id") is None
    assert quartieri.get("website_url") == "https://my.unical.it/"

    servizio_mensa = places["service-servizio-mensa"]
    assert servizio_mensa.get("building_id") is None
    assert servizio_mensa.get("opening_hours") == "Orari disponibili sulla pagina sorgente"

    martensson = buildings["mensa-martenson"]
    assert martensson.get("name") == "Mensa Quartiere Martensson"
    assert martensson.get("category") == "MENSA"
    assert "Pranzo: ore 12:00 - 15:00." in str(martensson.get("description"))
    assert "Cena: ore 19:00 - 21:30" in str(martensson.get("description"))
    assert martensson.get("source_url") == (
        "https://www.unical.it/campus/vivere-il-campus/servizio-mensa/"
    )

    piazza_vermicelli = buildings["mensa-piazza-vermicelli"]
    assert piazza_vermicelli.get("category") == "MENSA"
    assert piazza_vermicelli.get("description") == (
        "Aperta dal lunedi al venerdi. Pranzo: ore 12:00 - 15:00."
    )

    assert "mensa-maisonnettes-senior" not in buildings
    assert "mensa-martenson-ingresso" not in buildings
    assert "mensa-studenti-ingresso" not in buildings
    assert "quartiere-blocco-11-e-12" not in buildings
    assert "quartiere-monaci" not in buildings
    assert "quartiere-nervoso" not in buildings

    quartiere_monaci = places["quartiere-monaci"]
    assert quartiere_monaci.get("type") == "QUARTIERE"
    assert quartiere_monaci.get("description") is not None
    assert quartiere_monaci.get("email") == "roberto.bartucci@unical.it"
    assert quartiere_monaci.get("phone") == "338/2518197"
    assert quartiere_monaci.get("website_url") == "https://soscr.unical.it/"
    assert "Posti: 202." in str(quartiere_monaci.get("access_notes"))
    assert "Spazi comuni:" in str(quartiere_monaci.get("access_notes"))
    assert (
        "quartiere-monaci__has_child_building__quartiere-monaci" not in entity_links
    )
    assert (
        "quartiere-nervoso__has_child_building__quartiere-nervoso" not in entity_links
    )


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
