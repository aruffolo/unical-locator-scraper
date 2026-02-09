import json
from pathlib import Path

from unical_scraper.validate.integrity import check_integrity
from unical_scraper.validate.jsonschema_validate import validate_json_file


def test_validate_json_file_with_simple_schema(tmp_path: Path) -> None:
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["person_id", "full_name", "role"],
            "properties": {
                "person_id": {"type": "string"},
                "full_name": {"type": "string"},
                "role": {"type": "string"},
            },
            "additionalProperties": False,
        },
    }
    payload = [{"person_id": "rossi-mario", "full_name": "Mario Rossi", "role": "PROFESSOR"}]

    schema_path = tmp_path / "people.schema.json"
    data_path = tmp_path / "people.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    data_path.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_json_file(data_path=data_path, schema_path=schema_path)
    assert errors == []


def test_integrity_detects_missing_department_reference(tmp_path: Path) -> None:
    people = [
        {
            "person_id": "rossi-mario",
            "full_name": "Mario Rossi",
            "role": "PROFESSOR",
            "department_id": "dimes",
        }
    ]
    buildings = []
    departments = [{"department_id": "dic", "name": "Dipartimento di Chimica"}]
    places = []

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    assert len(issues) == 1
    assert "department_id 'dimes' does not exist" in issues[0].message


def test_integrity_detects_invalid_place_building_reference(tmp_path: Path) -> None:
    buildings = [{"building_id": "cubo-18b", "name": "Cubo 18B"}]
    departments = []
    people = []
    places = [
        {
            "place_id": "service-centro-sanitario",
            "type": "SERVICE",
            "name": "Centro Sanitario",
            "building_id": "cubo-34b",
        }
    ]

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    assert len(issues) == 1
    assert "building_id 'cubo-34b' does not exist" in issues[0].message


def test_integrity_detects_invalid_department_primary_building_reference(tmp_path: Path) -> None:
    buildings = [{"building_id": "cubo-18b", "name": "Cubo 18B"}]
    departments = [
        {
            "department_id": "dimes",
            "name": "DIMES",
            "primary_building_id": "cubo-34b",
        }
    ]
    people = []
    places = []

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    assert len(issues) == 1
    assert "primary_building_id 'cubo-34b' does not exist" in issues[0].message


def test_integrity_detects_invalid_aula_references(tmp_path: Path) -> None:
    buildings = [{"building_id": "cubo-18b", "name": "Cubo 18B"}]
    departments = [{"department_id": "dimes", "name": "DIMES"}]
    places = [
        {"place_id": "aula-p2", "type": "AULA", "name": "Aula P2", "building_id": "cubo-18b"},
        {"place_id": "service-1", "type": "SERVICE", "name": "Servizio 1"},
    ]
    people = []
    aulas = [
        {
            "aula_id": "aula-p2",
            "place_id": "aula-p2",
            "name": "Aula P2",
            "building_id": "cubo-34b",
            "department_id": "dimeg",
        },
        {
            "aula_id": "aula-service-wrong-type",
            "place_id": "service-1",
            "name": "Service Wrong Type",
        },
        {
            "aula_id": "aula-missing-place",
            "place_id": "missing-place",
            "name": "Missing Place",
        },
    ]

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "aulas.json").write_text(json.dumps(aulas), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    messages = [issue.message for issue in issues]

    assert any("building_id 'cubo-34b' does not exist" in message for message in messages)
    assert any("department_id 'dimeg' does not exist" in message for message in messages)
    assert any("place_id 'service-1' points to a non-AULA place" in message for message in messages)
    assert any("place_id 'missing-place' does not exist" in message for message in messages)
