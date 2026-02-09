from __future__ import annotations

from unical_scraper.transform.linking import link_places_to_buildings


def test_link_places_to_buildings_links_cubo_from_text() -> None:
    places = [
        {
            "place_id": "office-1",
            "type": "OFFICE",
            "name": "Ufficio tutorato",
            "description": "Ricevimento al Cubo 34B, piano terra",
        }
    ]
    buildings = [{"building_id": "cubo-34b", "name": "Cubo 34B"}]

    linked = link_places_to_buildings(places=places, buildings=buildings)

    assert linked[0]["building_id"] == "cubo-34b"


def test_link_places_to_buildings_links_known_keyword_routes() -> None:
    places = [
        {
            "place_id": "service-1",
            "type": "SERVICE",
            "name": "Centro Sanitario",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/centro-sanitario/",
        },
        {
            "place_id": "office-2",
            "type": "OFFICE",
            "name": "Front office on-line",
            "source_url": "https://www.unical.it/didattica/diritto-allo-studio/front-office-on-line-cr",
        },
    ]
    buildings = [
        {"building_id": "centro-sanitario", "name": "Centro Sanitario"},
        {
            "building_id": "uffici-centro-residenziale-e-area-didattica",
            "name": "Uffici Centro Residenziale e Area Didattica",
        },
    ]

    linked = link_places_to_buildings(places=places, buildings=buildings)

    assert linked[0]["building_id"] == "centro-sanitario"
    assert linked[1]["building_id"] == "uffici-centro-residenziale-e-area-didattica"


def test_link_places_to_buildings_links_additional_service_routes() -> None:
    places = [
        {
            "place_id": "service-cla",
            "type": "SERVICE",
            "name": "Centro Linguistico Di Ateneo",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/centro-linguistico-di-ateneo/",
        },
        {
            "place_id": "service-cus",
            "type": "SERVICE",
            "name": "Centro Sportivo",
            "description": "Centro Universitario Sportivo",
        },
        {
            "place_id": "service-career",
            "type": "SERVICE",
            "name": "Orientamento",
            "source_url": "https://www.unical.it/didattica/orientamento/career-service/",
        },
        {
            "place_id": "service-foresteria",
            "type": "SERVICE",
            "name": "Servizio Foresteria",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/servizio-foresteria/",
        },
    ]
    buildings = [
        {
            "building_id": "cla-centro-linguistico-d-ateneo",
            "name": "CLA - Centro Linguistico d'Ateneo",
        },
        {"building_id": "centro-universitario-sportivo", "name": "Centro Universitario Sportivo"},
        {"building_id": "cubi-7-11b", "name": "Cubi 7-11B"},
        {
            "building_id": "uffici-centro-residenziale-e-area-didattica",
            "name": "Uffici Centro Residenziale e Area Didattica",
        },
    ]

    linked = link_places_to_buildings(places=places, buildings=buildings)

    assert linked[0]["building_id"] == "cla-centro-linguistico-d-ateneo"
    assert linked[1]["building_id"] == "centro-universitario-sportivo"
    assert linked[2]["building_id"] == "cubi-7-11b"
    assert linked[3]["building_id"] == "uffici-centro-residenziale-e-area-didattica"


def test_link_places_to_buildings_links_reviewed_web_and_field_routes() -> None:
    places = [
        {
            "place_id": "service-biblioteche",
            "type": "SERVICE",
            "name": "Biblioteche",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/biblioteche/",
        },
        {
            "place_id": "service-polo-infanzia",
            "type": "SERVICE",
            "name": "Polo Infanzia",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/polo-infanzia/",
        },
        {
            "place_id": "service-teatri-e-cinema",
            "type": "SERVICE",
            "name": "Teatri E Cinema",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/teatri-e-cinema/",
        },
        {
            "place_id": "service-centro-congressi",
            "type": "SERVICE",
            "name": "Centro Congressi",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/centro-congressi/",
        },
        {
            "place_id": "service-servizi-ict",
            "type": "SERVICE",
            "name": "Servizi ICT",
            "source_url": "https://www.unical.it/servizi-ict/servizi-digitali-studenti/",
        },
        {
            "place_id": "service-servizio-mensa",
            "type": "SERVICE",
            "name": "Servizio Mensa",
            "source_url": "https://www.unical.it/campus/vivere-il-campus/servizio-mensa/",
        },
    ]
    buildings = [
        {"building_id": "cubo-libro", "name": "Cubo LIBRO"},
        {"building_id": "auditorium-teatro-grande", "name": "Auditorium Teatro Grande"},
        {"building_id": "aula-magna", "name": "Aula Magna"},
        {"building_id": "cubo-22b", "name": "Cubo 22B"},
        {
            "building_id": "uffici-centro-residenziale-e-area-didattica",
            "name": "Uffici Centro Residenziale e Area Didattica",
        },
    ]

    linked = link_places_to_buildings(places=places, buildings=buildings)

    assert linked[0]["building_id"] == "cubo-libro"
    assert linked[1]["building_id"] == "auditorium-teatro-grande"
    assert linked[2]["building_id"] == "auditorium-teatro-grande"
    assert linked[3]["building_id"] == "aula-magna"
    assert linked[4]["building_id"] == "cubo-22b"
    assert linked[5]["building_id"] == "uffici-centro-residenziale-e-area-didattica"
