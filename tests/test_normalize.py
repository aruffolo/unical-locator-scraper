from datetime import datetime, timezone

from unical_scraper.extract.aulas import RawAula
from unical_scraper.extract.buildings import RawBuilding
from unical_scraper.extract.departments import RawDepartment
from unical_scraper.extract.services import RawService
from unical_scraper.extract.teachers import RawTeacher
from unical_scraper.transform.normalize import (
    normalize_aulas,
    normalize_buildings,
    normalize_departments,
    normalize_services,
    normalize_teachers,
)


def test_normalize_teachers_produces_people_schema_shape() -> None:
    raw = [
        RawTeacher(
            full_name="Francesco Scarcello",
            email="francesco.scarcello@unical.it",
            department_name="DIMES",
            source_url="https://www.unical.it/docenti/francesco-scarcello",
            website_url="https://www.unical.it/docenti/francesco-scarcello",
            office_hours="Martedi 10:00 - 12:00",
        )
    ]

    people = normalize_teachers(
        raw_teachers=raw,
        verified_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    person = people[0]
    assert person["person_id"] == "scarcello-francesco"
    assert person["full_name"] == "Francesco Scarcello"
    assert person["role"] == "PROFESSOR"
    assert person["department_id"] == "dimes"
    assert person["source_id"] == "unical-teachers"
    assert person["last_verified_at"] == "2026-02-09T00:00:00+00:00"


def test_normalize_departments_produces_departments_schema_shape() -> None:
    raw = [
        RawDepartment(
            name="Dipartimento di Ingegneria Informatica, Modellistica, Elettronica e Sistemistica",
            source_url="https://www.unical.it/ateneo/dipartimenti/dimes",
            email="segreteria@dimes.unical.it",
            phone="+39 0984 123456",
            website_url="https://dimes.unical.it",
        )
    ]

    departments = normalize_departments(
        raw_departments=raw,
        verified_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
    )

    assert len(departments) == 1
    department = departments[0]
    assert department["department_id"] == "dipartimento-di-ingegneria-informatica-modellistica-elettronica-e-sistemistica"
    assert department["name"] == raw[0].name
    assert department["email"] == "segreteria@dimes.unical.it"
    assert department["source_id"] == "unical-departments"
    assert department["last_verified_at"] == "2026-02-09T00:00:00+00:00"


def test_normalize_services_produces_places_schema_shape() -> None:
    raw = [
        RawService(
            name="Segreteria Studenti DIMES",
            source_url="https://www.unical.it/servizi/segreteria-dimes",
            service_type="SECRETARY",
            description="Supporto iscrizioni e certificati.",
            email="segreteria@unical.it",
            phone="+39 0984 111111",
            website_url="https://www.unical.it/servizi/segreteria-dimes",
            opening_hours="Lun-Ven 09:00-12:00",
        )
    ]

    places = normalize_services(
        raw_services=raw,
        verified_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
    )

    assert len(places) == 1
    place = places[0]
    assert place["place_id"] == "secretary-segreteria-studenti-dimes"
    assert place["type"] == "SECRETARY"
    assert place["name"] == "Segreteria Studenti DIMES"
    assert place["email"] == "segreteria@unical.it"
    assert place["source_id"] == "unical-services"
    assert place["last_verified_at"] == "2026-02-09T00:00:00+00:00"


def test_normalize_buildings_produces_buildings_schema_shape() -> None:
    raw = [
        RawBuilding(
            name="Cubo 18B - DiCES",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            lat=39.360596123,
            lng=16.226684612,
            description="Dipartimento di Culture, Educazione e Societa",
        ),
        RawBuilding(
            name="Cubo 18B",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            lat=39.360500000,
            lng=16.226600000,
        ),
    ]

    buildings = normalize_buildings(
        raw_buildings=raw,
        verified_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
    )

    assert len(buildings) == 1
    building = buildings[0]
    assert building["building_id"] == "cubo-18b"
    assert building["name"] == "Cubo 18B"
    assert building["source_id"] == "unical-campus-map"
    assert building["last_verified_at"] == "2026-02-09T00:00:00+00:00"


def test_normalize_aulas_produces_aulas_and_aula_places() -> None:
    raw = [
        RawAula(
            name="Aula A G",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            lat=39.3605961,
            lng=16.2266846,
            floor="Piano Terra",
            room="A G",
            short_code="AG",
            building_hint="Cubo 40C",
            capacity=117,
        ),
        RawAula(
            name="Aula Magna",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            lat=39.3583149,
            lng=16.2258276,
        ),
    ]
    buildings = [
        {"building_id": "cubo-40c", "name": "Cubo 40C", "lat": 39.3605960, "lng": 16.2266845},
        {"building_id": "aula-magna", "name": "Aula Magna", "lat": 39.3583150, "lng": 16.2258277},
    ]

    aulas, aula_places = normalize_aulas(
        raw_aulas=raw,
        buildings=buildings,
        verified_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
    )

    assert len(aulas) == 2
    assert len(aula_places) == 2

    aula_by_short = {aula.get("short_code"): aula for aula in aulas}
    aula_ag = aula_by_short["AG"]
    assert aula_ag["building_id"] == "cubo-40c"
    assert aula_ag["place_id"] == aula_ag["aula_id"]
    assert aula_ag["normalized_name"] == "aula a g"
    assert aula_ag["capacity"] == 117
    assert "ag" in aula_ag["search_tokens"]

    aula_magna = next(aula for aula in aulas if aula["name"] == "Aula Magna")
    assert aula_magna["building_id"] == "aula-magna"

    place_by_id = {place["place_id"]: place for place in aula_places}
    assert place_by_id[aula_ag["aula_id"]]["type"] == "AULA"
    assert place_by_id[aula_magna["aula_id"]]["building_id"] == "aula-magna"


def test_normalize_aulas_backfills_building_id_from_existing_matches() -> None:
    raw = [
        RawAula(
            name="AULA 2",
            source_url="https://planner.example/activities/",
            room="2",
        ),
        RawAula(
            name="Aula 2",
            source_url="https://department.example/strutture/",
            room="2",
            building_hint="Cubo 12B",
        ),
        RawAula(
            name="Aula 39C",
            source_url="https://department.example/strutture/",
            room="39C",
        ),
    ]
    buildings = [
        {"building_id": "cubo-12b", "name": "Cubo 12B"},
        {"building_id": "cubo-39c", "name": "Cubo 39C"},
    ]

    aulas, aula_places = normalize_aulas(
        raw_aulas=raw,
        buildings=buildings,
        verified_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
    )

    aula_upper = next(aula for aula in aulas if aula["name"] == "AULA 2")
    assert aula_upper["building_id"] == "cubo-12b"
    assert "cubo-12b" in aula_upper["search_tokens"]

    aula_39c = next(aula for aula in aulas if aula["name"] == "Aula 39C")
    assert aula_39c["building_id"] == "cubo-39c"

    place_by_id = {place["place_id"]: place for place in aula_places}
    assert place_by_id[aula_upper["place_id"]]["building_id"] == "cubo-12b"
    assert place_by_id[aula_39c["place_id"]]["building_id"] == "cubo-39c"
