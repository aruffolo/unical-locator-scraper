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


def test_integrity_detects_invalid_alias_references(tmp_path: Path) -> None:
    buildings = [{"building_id": "cubo-18b", "name": "Cubo 18B"}]
    departments = [{"department_id": "dimes", "name": "DIMES"}]
    people = [{"person_id": "rossi-mario", "full_name": "Mario Rossi", "role": "PROFESSOR"}]
    places = [{"place_id": "aula-p2", "type": "AULA", "name": "Aula P2"}]
    aulas = [{"aula_id": "aula-p2", "place_id": "aula-p2", "name": "Aula P2"}]
    aliases = [
        {"alias_id": "ok-place", "entity_type": "PLACE", "entity_id": "aula-p2", "label": "P2"},
        {"alias_id": "bad-place", "entity_type": "PLACE", "entity_id": "missing-place", "label": "P 2"},
        {"alias_id": "bad-building", "entity_type": "BUILDING", "entity_id": "missing-building", "label": "Cubo 99"},
    ]

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "aulas.json").write_text(json.dumps(aulas), encoding="utf-8")
    (tmp_path / "aliases.json").write_text(json.dumps(aliases), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    messages = [issue.message for issue in issues]

    assert any("entity_id 'missing-place' does not exist for entity_type 'PLACE'" in message for message in messages)
    assert any(
        "entity_id 'missing-building' does not exist for entity_type 'BUILDING'" in message
        for message in messages
    )


def test_integrity_detects_duplicate_aula_identity_key(tmp_path: Path) -> None:
    buildings = [{"building_id": "cubo-12b", "name": "Cubo 12B"}]
    departments = []
    people = []
    places = [
        {"place_id": "aula-2", "type": "AULA", "name": "Aula 2", "building_id": "cubo-12b"},
        {"place_id": "aula-2-cubo-12b", "type": "AULA", "name": "Aula 2", "building_id": "cubo-12b"},
    ]
    aulas = [
        {
            "aula_id": "aula-2",
            "place_id": "aula-2",
            "name": "AULA 2",
            "normalized_name": "aula 2",
            "building_id": "cubo-12b",
        },
        {
            "aula_id": "aula-2-cubo-12b",
            "place_id": "aula-2-cubo-12b",
            "name": "Aula 2",
            "normalized_name": "aula 2",
            "building_id": "cubo-12b",
        },
    ]

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "aulas.json").write_text(json.dumps(aulas), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    messages = [issue.message for issue in issues]
    assert any("duplicate aula key for normalized_name 'aula 2'" in message for message in messages)


def test_integrity_detects_conflicting_floor_for_same_room_and_building(tmp_path: Path) -> None:
    buildings = [{"building_id": "cubo-30b", "name": "Cubo 30B"}]
    departments = []
    people = []
    places = [
        {"place_id": "aula-mt1-a", "type": "AULA", "name": "Aula MT1", "building_id": "cubo-30b"},
        {"place_id": "aula-mt1-b", "type": "AULA", "name": "Aula MT1", "building_id": "cubo-30b"},
    ]
    aulas = [
        {
            "aula_id": "aula-mt1-a",
            "place_id": "aula-mt1-a",
            "name": "Aula MT1",
            "normalized_name": "aula mt1",
            "building_id": "cubo-30b",
            "room": "MT1",
            "floor": "Piano Terra",
        },
        {
            "aula_id": "aula-mt1-b",
            "place_id": "aula-mt1-b",
            "name": "Aula MT1",
            "normalized_name": "mt1 aula",
            "building_id": "cubo-30b",
            "room": "MT1",
            "floor": "Secondo piano",
        },
    ]

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "aulas.json").write_text(json.dumps(aulas), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    messages = [issue.message for issue in issues]
    assert any("conflicting floor for room 'mt1'" in message for message in messages)


def test_integrity_detects_suspicious_near_duplicate_aulas_by_token_set(tmp_path: Path) -> None:
    buildings = [{"building_id": "cubo-29b", "name": "Cubo 29B"}]
    departments = []
    people = []
    places = [
        {"place_id": "aula-dolci-a", "type": "AULA", "name": "Aula 29B1 - D. Dolci", "building_id": "cubo-29b"},
        {"place_id": "aula-dolci-b", "type": "AULA", "name": "29B1 D Dolci Aula", "building_id": "cubo-29b"},
    ]
    aulas = [
        {
            "aula_id": "aula-dolci-a",
            "place_id": "aula-dolci-a",
            "name": "Aula 29B1 - D. Dolci",
            "normalized_name": "aula 29b1 d dolci",
            "building_id": "cubo-29b",
            "room": "29B1",
            "floor": "Primo piano",
        },
        {
            "aula_id": "aula-dolci-b",
            "place_id": "aula-dolci-b",
            "name": "29B1 D Dolci Aula",
            "normalized_name": "29b1 dolci d aula",
            "building_id": "cubo-29b",
            "room": "29B1X",
            "floor": "Primo piano",
        },
    ]

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "aulas.json").write_text(json.dumps(aulas), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    near_dup_issues = [issue for issue in issues if issue.level == "warning"]
    assert any("suspicious near-duplicate aulas" in issue.message for issue in near_dup_issues)


def test_integrity_detects_invalid_entity_link_references(tmp_path: Path) -> None:
    buildings = [{"building_id": "mensa-maisonnettes", "name": "Mensa Quartiere Maisonnettes"}]
    departments = []
    people = []
    places = [{"place_id": "service-quartieri", "type": "SERVICE", "name": "Quartieri"}]
    aulas = []
    aliases = []
    entity_links = [
        {
            "link_id": "service-quartieri__has_child_place__quartiere-missing",
            "parent_entity_type": "PLACE",
            "parent_entity_id": "service-quartieri",
            "relation_type": "HAS_CHILD_PLACE",
            "child_entity_type": "PLACE",
            "child_entity_id": "quartiere-missing",
        },
        {
            "link_id": "missing-parent__has_child_building__mensa-maisonnettes",
            "parent_entity_type": "PLACE",
            "parent_entity_id": "missing-parent",
            "relation_type": "HAS_CHILD_BUILDING",
            "child_entity_type": "BUILDING",
            "child_entity_id": "mensa-maisonnettes",
        },
    ]

    (tmp_path / "buildings.json").write_text(json.dumps(buildings), encoding="utf-8")
    (tmp_path / "departments.json").write_text(json.dumps(departments), encoding="utf-8")
    (tmp_path / "places.json").write_text(json.dumps(places), encoding="utf-8")
    (tmp_path / "people.json").write_text(json.dumps(people), encoding="utf-8")
    (tmp_path / "aulas.json").write_text(json.dumps(aulas), encoding="utf-8")
    (tmp_path / "aliases.json").write_text(json.dumps(aliases), encoding="utf-8")
    (tmp_path / "entity_links.json").write_text(json.dumps(entity_links), encoding="utf-8")

    issues = check_integrity(data_dir=tmp_path)
    messages = [issue.message for issue in issues]

    assert any("child_entity_id 'quartiere-missing' does not exist" in message for message in messages)
    assert any("parent_entity_id 'missing-parent' does not exist" in message for message in messages)
