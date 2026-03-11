from datetime import datetime, timezone

from unical_scraper.extract.aulas import RawAula
from unical_scraper.extract.buildings import RawBuilding
from unical_scraper.extract.departments import RawDepartment
from unical_scraper.extract.services import RawService
from unical_scraper.extract.teachers import RawTeacher
from unical_scraper.transform.normalize import (
    normalize_teacher_office_places,
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


def test_normalize_teachers_resolves_department_id_from_department_dataset() -> None:
    raw = [
        RawTeacher(
            full_name="Mario Rossi",
            department_name="DIMES",
            source_url="https://www.unical.it/storage/teachers/mario.rossi/",
        )
    ]
    departments = [
        {
            "department_id": "dipartimento-di-ingegneria-informatica-modellistica-elettronica-e-sistemistica",
            "name": "Dipartimento di Ingegneria Informatica, Modellistica, Elettronica e Sistemistica",
            "source_url": "https://www.unical.it/ateneo/dipartimenti/dimes",
        }
    ]

    people = normalize_teachers(
        raw_teachers=raw,
        departments=departments,
        verified_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    assert (
        people[0]["department_id"]
        == "dipartimento-di-ingegneria-informatica-modellistica-elettronica-e-sistemistica"
    )


def test_normalize_teachers_resolves_department_id_from_email_domain_alias() -> None:
    raw = [
        RawTeacher(
            full_name="Marta B",
            email="marta.b@dimes.unical.it",
            source_url="https://www.unical.it/storage/teachers/marta.b/",
        ),
        RawTeacher(
            full_name="Carlo F",
            email="carlo.f@fis.unical.it",
            source_url="https://www.unical.it/storage/teachers/carlo.f/",
        ),
    ]
    departments = [
        {
            "department_id": "dipartimento-di-ingegneria-informatica-modellistica-elettronica-e-sistemistica",
            "name": "Dipartimento di Ingegneria Informatica, Modellistica, Elettronica e Sistemistica",
            "source_url": "https://www.unical.it/ateneo/dipartimenti/dimes",
        },
        {
            "department_id": "dipartimento-di-fisica",
            "name": "Dipartimento di Fisica",
            "source_url": "https://www.unical.it/ateneo/dipartimenti/df",
        },
    ]

    people = normalize_teachers(
        raw_teachers=raw,
        departments=departments,
        verified_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
    )
    by_name = {p["full_name"]: p for p in people}

    assert (
        by_name["Marta B"]["department_id"]
        == "dipartimento-di-ingegneria-informatica-modellistica-elettronica-e-sistemistica"
    )
    assert by_name["Carlo F"]["department_id"] == "dipartimento-di-fisica"


def test_normalize_teachers_resolves_department_id_from_department_teacher_map() -> None:
    raw = [
        RawTeacher(
            full_name="Giulia Neri",
            email="giulia.neri@unical.it",
            website_url="https://www.unical.it/storage/teachers/giulia.neri/",
            source_url="https://www.unical.it/storage/teachers/giulia.neri/",
        )
    ]
    mapping = {"slug:giulia.neri": "dipartimento-di-matematica-e-informatica"}

    people = normalize_teachers(
        raw_teachers=raw,
        departments=[],
        department_teacher_map=mapping,
        verified_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    assert people[0]["department_id"] == "dipartimento-di-matematica-e-informatica"


def test_normalize_teachers_resolves_department_id_from_encoded_teacher_slug() -> None:
    raw = [
        RawTeacher(
            full_name="Encrypted Profile",
            source_url=(
                "https://www.unical.it/storage/teachers/"
                "gAAAAABpjRXoV34BdbpbKEeVOdE_nUevks5Z9XrOw_k0ZVaXo3n9YfHp%3D%3D/"
            ),
        )
    ]
    mapping = {
        "slug:gaaaaabpjrxov34bdbpbkeevode_nuevks5z9xrow_k0zvaxo3n9yfhp==": "dipartimento-di-fisica"
    }
    people = normalize_teachers(
        raw_teachers=raw,
        departments=[],
        department_teacher_map=mapping,
        verified_at=datetime(2026, 2, 12, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    assert people[0]["department_id"] == "dipartimento-di-fisica"


def test_normalize_teachers_resolves_department_id_from_unique_name_map() -> None:
    raw = [
        RawTeacher(
            full_name="Mario Rossi",
            source_url="https://www.unical.it/storage/teachers/unknown/",
        )
    ]
    mapping = {"name:mario rossi": "dipartimento-di-fisica"}
    people = normalize_teachers(
        raw_teachers=raw,
        departments=[],
        department_teacher_map=mapping,
        verified_at=datetime(2026, 2, 12, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    assert people[0]["department_id"] == "dipartimento-di-fisica"


def test_normalize_teachers_resolves_department_id_from_name_key_map() -> None:
    raw = [
        RawTeacher(
            full_name="Prof.ssa Anna Maria C. Napoli",
            source_url="https://www.unical.it/storage/teachers/unknown/",
        )
    ]
    mapping = {"name_key:anna-maria-napoli": "dipartimento-di-chimica-e-tecnologie-chimiche"}
    people = normalize_teachers(
        raw_teachers=raw,
        departments=[],
        department_teacher_map=mapping,
        verified_at=datetime(2026, 2, 12, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    assert people[0]["department_id"] == "dipartimento-di-chimica-e-tecnologie-chimiche"


def test_normalize_teachers_resolves_department_id_from_department_code_map() -> None:
    raw = [
        RawTeacher(
            full_name="Mario Rossi",
            department_code="002019",
            source_url="https://www.unical.it/storage/teachers/unknown/",
        )
    ]
    mapping = {"department_code:002019": "dipartimento-di-fisica"}
    people = normalize_teachers(
        raw_teachers=raw,
        departments=[],
        department_teacher_map=mapping,
        verified_at=datetime(2026, 2, 12, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    assert people[0]["department_id"] == "dipartimento-di-fisica"


def test_normalize_teacher_office_places_generates_structured_office_records() -> None:
    raw = [
        RawTeacher(
            full_name="Rosa Adamo",
            source_url="https://www.unical.it/storage/teachers/rosa.adamo/",
            office_reference="Cubo 3C Piano 2 Stanza 8",
            office_hours="Lunedi 10:00-12:00",
            notes="Office references: Cubo 3C Piano 2 Stanza 8",
        ),
        RawTeacher(
            full_name="No Structured Office",
            source_url="https://www.unical.it/storage/teachers/no-office/",
            office_reference="Direzione Generale",
        ),
    ]

    places = normalize_teacher_office_places(
        raw_teachers=raw,
        existing_places=[],
        buildings=[{"building_id": "cubo-3c", "name": "Cubo 3C"}],
        verified_at=datetime(2026, 2, 11, tzinfo=timezone.utc),
    )

    assert len(places) == 1
    place = places[0]
    assert place["type"] == "OFFICE"
    assert place["building_id"] == "cubo-3c"
    assert place["floor"] == "Piano 2"
    assert place["room"] == "Stanza 8"


def test_normalize_teacher_office_places_maps_edificio_patterns_to_buildings() -> None:
    raw = [
        RawTeacher(
            full_name="Mario Uno",
            source_url="https://www.unical.it/storage/teachers/mario-uno/",
            office_reference="Edificio Centro Sanitario",
        ),
        RawTeacher(
            full_name="Mario Due",
            source_url="https://www.unical.it/storage/teachers/mario-due/",
            office_reference="Edificio Polifunzionale",
        ),
        RawTeacher(
            full_name="Mario Tre",
            source_url="https://www.unical.it/storage/teachers/mario-tre/",
            office_reference="Edificio Museo di Storia Naturale e Orto Botanico",
        ),
    ]

    places = normalize_teacher_office_places(
        raw_teachers=raw,
        existing_places=[],
        buildings=[
            {"building_id": "centro-sanitario", "name": "Centro Sanitario"},
            {"building_id": "polifunzionale", "name": "Edificio Polifunzionale"},
            {"building_id": "orto-botanico", "name": "Museo di Storia Naturale e Orto Botanico"},
        ],
        verified_at=datetime(2026, 2, 12, tzinfo=timezone.utc),
    )

    assert len(places) == 3
    by_name = {str(item["name"]): item for item in places}
    assert by_name["Ufficio Edificio Centro Sanitario"]["building_id"] == "centro-sanitario"
    assert by_name["Ufficio Edificio Polifunzionale"]["building_id"] == "polifunzionale"
    assert (
        by_name["Ufficio Edificio Museo di Storia Naturale e Orto Botanico"]["building_id"]
        == "orto-botanico"
    )


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


def test_normalize_buildings_cleans_map_metadata_descriptions_without_dropping_entities() -> None:
    raw = [
        RawBuilding(
            name="Palestra CUS",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            lat=39.3625000,
            lng=16.2261000,
            description="Aule/zone coperte da WiFi: Zona Copertura Outdoor: Punto-Punto",
        ),
        RawBuilding(
            name="Cubo 1B",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            lat=39.3605000,
            lng=16.2266000,
            description=(
                "Descrizione: Dipartimento di Scienze Politiche e Sociali "
                "Link informativo: http://example.test/ "
                "Piano Terra: Primo piano:"
            ),
        ),
        RawBuilding(
            name="Cappella Universitaria",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            lat=39.3615853,
            lng=16.2262273,
            description="Landmark on official UNICAL campus map (area Cubo 24B)",
        ),
    ]

    buildings = normalize_buildings(
        raw_buildings=raw,
        verified_at=datetime(2026, 2, 13, tzinfo=timezone.utc),
    )

    assert len(buildings) == 3
    by_id = {item["building_id"]: item for item in buildings}
    assert "description" not in by_id["palestra-cus"]
    assert by_id["cubo-1b"]["description"] == "Dipartimento di Scienze Politiche e Sociali"
    assert "description" not in by_id["cappella-universitaria"]


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

    aula_two = next(aula for aula in aulas if aula["normalized_name"] == "aula 2")
    assert aula_two["building_id"] == "cubo-12b"
    assert aula_two["name"] == "Aula 2"
    assert "cubo-12b" in aula_two["search_tokens"]

    aula_39c = next(aula for aula in aulas if aula["name"] == "Aula 39C")
    assert aula_39c["building_id"] == "cubo-39c"

    place_by_id = {place["place_id"]: place for place in aula_places}
    assert place_by_id[aula_two["place_id"]]["building_id"] == "cubo-12b"
    assert place_by_id[aula_39c["place_id"]]["building_id"] == "cubo-39c"


def test_normalize_aulas_applies_manual_overrides_and_drops_known_false_positives() -> None:
    planner_source = "https://unical.prod.up.cineca.it/calendar/activities/"
    raw = [
        RawAula(
            name="Aula Studio per i soli studenti di Chimica",
            source_url="https://ctc.unical.it/dipartimento/organizzazione/strutture/",
        ),
        RawAula(
            name="Aula Dolci",
            source_url="https://dices.unical.it/dipartimento/organizzazione/strutture/",
        ),
        RawAula(
            name="Aula LIME Laboratory of Innovation and Management Engineering",
            source_url="https://dimeg.unical.it/dipartimento/organizzazione/strutture/",
        ),
        RawAula(
            name="Aula seminari (Giannattasio)",
            source_url="https://dinci.unical.it/dipartimento/organizzazione/strutture/",
        ),
        RawAula(
            name="AULA MULTIMEDIALE 25 C SELF STUDY",
            source_url=planner_source,
        ),
        RawAula(
            name="Aula Multimediale piano 1°cubo 25C",
            source_url=planner_source,
            floor="Primo piano",
        ),
        RawAula(
            name="Aula Multimediale CLA 25C",
            source_url="https://cla.unical.it/servizi-linguistici/studio-in-autonomia/",
            building_hint="Cubo 25C",
        ),
        RawAula(
            name="aula e",
            source_url="https://dimes.unical.it/dipartimento/organizzazione/strutture/",
        ),
        RawAula(name="Aula Blu", source_url=planner_source),
        RawAula(name="Aula Verde", source_url=planner_source),
        RawAula(name="Laboratorio A", source_url=planner_source),
        RawAula(name="Laboratorio B", source_url=planner_source),
        RawAula(name="Laboratorio C", source_url=planner_source),
        RawAula(name="SPAZIO MOSTRE", source_url=planner_source),
    ]
    buildings = [
        {"building_id": "cubo-15c", "name": "Cubo 15C"},
        {"building_id": "cubo-29b", "name": "Cubo 29B"},
        {"building_id": "cubo-41c", "name": "Cubo 41C"},
        {"building_id": "cubo-45b", "name": "Cubo 45B"},
        {"building_id": "cla-centro-linguistico-d-ateneo", "name": "CLA"},
    ]

    aulas, aula_places = normalize_aulas(
        raw_aulas=raw,
        buildings=buildings,
        verified_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
    )
    aula_by_name = {str(aula["name"]): aula for aula in aulas}

    assert "aula e" not in aula_by_name
    assert "Aula Blu" not in aula_by_name
    assert "Aula Verde" not in aula_by_name
    assert "Laboratorio A" not in aula_by_name
    assert "Laboratorio B" not in aula_by_name
    assert "Laboratorio C" not in aula_by_name
    assert "SPAZIO MOSTRE" not in aula_by_name

    chimica = aula_by_name["Aula Studio per i soli studenti di Chimica"]
    assert chimica["building_id"] == "cubo-15c"
    assert chimica["floor"] == "Secondo piano"

    dolci = aula_by_name["Aula Dolci"]
    assert dolci["building_id"] == "cubo-29b"
    assert dolci["floor"] == "Secondo piano"
    assert dolci["capacity"] == 280

    lime = aula_by_name["Aula LIME Laboratory of Innovation and Management Engineering"]
    assert lime["building_id"] == "cubo-41c"

    giannattasio = aula_by_name["Aula seminari (Giannattasio)"]
    assert giannattasio["building_id"] == "cubo-45b"
    assert giannattasio["floor"] == "Primo piano"

    self_study = aula_by_name["AULA MULTIMEDIALE 25 C SELF STUDY"]
    assert self_study["building_id"] == "cla-centro-linguistico-d-ateneo"

    multimediale = aula_by_name["Aula Multimediale piano 1°cubo 25C"]
    assert multimediale["building_id"] == "cla-centro-linguistico-d-ateneo"
    assert multimediale["floor"] == "Primo piano"

    cla_multimediale = aula_by_name["Aula Multimediale CLA 25C"]
    assert cla_multimediale["building_id"] == "cla-centro-linguistico-d-ateneo"

    place_names = {str(place["name"]) for place in aula_places}
    assert "Aula Blu" not in place_names
    assert "SPAZIO MOSTRE" not in place_names


def test_normalize_aulas_defaults_capannone_floor_to_ground() -> None:
    raw = [
        RawAula(
            name="Aula 45",
            source_url="https://www.unical.it/campus/visita-il-campus/mappa/",
            building_hint="Capannone F",
        )
    ]
    buildings = [{"building_id": "capannone-f", "name": "Capannone F"}]

    aulas, aula_places = normalize_aulas(
        raw_aulas=raw,
        buildings=buildings,
        verified_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
    )

    assert len(aulas) == 1
    assert aulas[0]["building_id"] == "capannone-f"
    assert aulas[0]["floor"] == "Piano Terra"

    assert len(aula_places) == 1
    assert aula_places[0]["building_id"] == "capannone-f"
    assert aula_places[0]["floor"] == "Piano Terra"


def test_normalize_aulas_applies_floor_overrides_from_dimes_dimeg_pages() -> None:
    raw = [
        RawAula(
            name="Aula DS5",
            source_url="https://dimes.unical.it/dipartimento/organizzazione/strutture/",
            building_hint="Cubo 41B",
        ),
        RawAula(
            name="Aula P5",
            source_url="https://dimes.unical.it/dipartimento/organizzazione/strutture/",
            building_hint="Cubo 43B",
        ),
        RawAula(
            name="Aula P3",
            source_url="https://dimeg.unical.it/dipartimento/organizzazione/strutture/",
            building_hint="Cubo 43C",
        ),
        RawAula(
            name="Aula Consolidata B",
            source_url="https://dimeg.unical.it/dipartimento/organizzazione/strutture/",
            building_hint="Cubo 43C",
        ),
    ]
    buildings = [
        {"building_id": "cubo-41b", "name": "Cubo 41B"},
        {"building_id": "cubo-43b", "name": "Cubo 43B"},
        {"building_id": "cubo-43c", "name": "Cubo 43C"},
    ]

    aulas, _ = normalize_aulas(
        raw_aulas=raw,
        buildings=buildings,
        verified_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
    )
    by_name = {str(aula["name"]): aula for aula in aulas}

    assert by_name["Aula DS5"]["floor"] == "Secondo piano"
    assert by_name["Aula P5"]["floor"] == "Sesto piano"
    assert by_name["Aula P3"]["floor"] == "Sesto piano"
    assert by_name["Aula Consolidata B"]["floor"] == "Quarto piano"


def test_normalize_aulas_infers_floor_from_code_hints() -> None:
    raw = [
        RawAula(
            name="CH-15-6A-3T",
            source_url="https://unical.prod.up.cineca.it/calendar/activities/",
            building_hint="Cubo 15C",
        ),
        RawAula(
            name="Lab 15C_3P",
            source_url="https://unical.prod.up.cineca.it/calendar/activities/",
            building_hint="Cubo 15C",
        ),
        RawAula(
            name="Aula 45B01",
            room="45B01",
            source_url="https://unical.prod.up.cineca.it/calendar/activities/",
            building_hint="Cubo 45B",
        ),
        RawAula(
            name="Aula P1 (Piano Ponte Carrabile)",
            source_url="https://dimeg.unical.it/dipartimento/organizzazione/strutture/",
            building_hint="Cubo 40C",
        ),
        RawAula(
            name="Aula 29B1 - D. Dolci",
            source_url="https://unical.prod.up.cineca.it/calendar/activities/",
            building_hint="Cubo 29B",
        ),
    ]
    buildings = [
        {"building_id": "cubo-15c", "name": "Cubo 15C"},
        {"building_id": "cubo-45b", "name": "Cubo 45B"},
        {"building_id": "cubo-40c", "name": "Cubo 40C"},
        {"building_id": "cubo-29b", "name": "Cubo 29B"},
    ]

    aulas, _ = normalize_aulas(
        raw_aulas=raw,
        buildings=buildings,
        verified_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
    )
    by_name = {str(aula["name"]): aula for aula in aulas}

    assert by_name["CH-15-6A-3T"]["floor"] == "Sesto piano"
    assert by_name["Lab 15C_3P"]["floor"] == "Terzo piano"
    assert by_name["Aula 45B01"]["floor"] == "Piano Terra"
    assert by_name["Aula P1 (Piano Ponte Carrabile)"]["floor"] == "Sesto piano"
    assert by_name["Aula 29B1 - D. Dolci"]["floor"] == "Primo piano"


def test_normalize_aulas_applies_semantic_floor_overrides_for_superiore_inferiore() -> None:
    planner_source = "https://unical.prod.up.cineca.it/calendar/activities/"
    raw = [
        RawAula(
            name="Aula Gialla - A (superiore)",
            source_url=planner_source,
            building_hint="Polifunzionale",
        ),
        RawAula(
            name="Aula Gialla - B (inferiore)",
            source_url=planner_source,
            building_hint="Polifunzionale",
        ),
        RawAula(
            name='AULA SEMINARI "GIANNATTASIO"',
            source_url=planner_source,
            building_hint="Cubo 45B",
        ),
    ]
    buildings = [
        {"building_id": "polifunzionale-dfssn", "name": "Polifunzionale"},
        {"building_id": "cubo-45b", "name": "Cubo 45B"},
    ]

    aulas, _ = normalize_aulas(
        raw_aulas=raw,
        buildings=buildings,
        verified_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
    )
    by_name = {str(aula["name"]): aula for aula in aulas}

    assert by_name["Aula Gialla - A (superiore)"]["floor"] == "Primo piano"
    assert by_name["Aula Gialla - B (inferiore)"]["floor"] == "Piano Terra"
    assert by_name['AULA SEMINARI "GIANNATTASIO"']["floor"] == "Primo piano"
