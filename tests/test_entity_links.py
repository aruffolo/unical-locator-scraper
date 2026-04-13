from __future__ import annotations

from datetime import datetime, timezone

from unical_scraper.transform.entity_links import apply_service_location_contract


def test_apply_service_location_contract_updates_overviews_and_children() -> None:
    places = [
        {
            "place_id": "service-quartieri",
            "type": "SERVICE",
            "name": "Quartieri",
            "building_id": "uffici-centro-residenziale-e-area-didattica",
        },
        {
            "place_id": "service-servizio-mensa",
            "type": "SERVICE",
            "name": "Servizio Mensa",
            "building_id": "uffici-centro-residenziale-e-area-didattica",
        },
        {
            "place_id": "service-centro-congressi",
            "type": "SERVICE",
            "name": "Centro Congressi",
            "building_id": "aula-magna",
        },
        {
            "place_id": "service-biblioteche",
            "type": "SERVICE",
            "name": "Biblioteche",
            "building_id": "cubo-libro",
        },
    ]
    buildings = [
        {"building_id": "mensa-maisonnettes", "name": "Mensa Maisonnettes"},
        {"building_id": "mensa-martenson", "name": "Mensa Martenson"},
        {"building_id": "mensa-maisonnettes-senior", "name": "Mensa Maisonnettes Senior"},
        {"building_id": "quartiere-monaci", "name": "Quartiere Monaci"},
        {"building_id": "maisonnettes", "name": "Maisonnettes"},
        {"building_id": "aula-magna", "name": "Aula Magna"},
    ]
    contract = {
        "clear_overview_building_ids": [
            "service-quartieri",
            "service-servizio-mensa",
            "service-centro-congressi",
            "service-biblioteche",
        ],
        "quartieri_places": [
            {
                "place_id": "quartiere-maisonnettes",
                "type": "QUARTIERE",
                "name": "Quartiere Maisonnettes",
                "lat": 39.3555355,
                "lng": 16.2229899,
                "description": "Complesso residenziale del campus.",
                "email": "mariarosa.spinaiaconis@unical.it",
                "phone": "346/3668313",
                "website_url": "https://soscr.unical.it/",
                "access_notes": "Posti: 519. Servizi: Internet Wi-Fi.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/quartieri/",
            }
        ],
        "place_overrides": [
            {
                "place_id": "service-biblioteche",
                "type": "SERVICE",
                "name": "Biblioteche",
                "description": "Sistema bibliotecario di Ateneo.",
                "website_url": "https://sba.unical.it/",
                "opening_hours": "Da lunedì a giovedì 09:00-20:05. Venerdì 09:00-17:00. Sabato chiuso.",
                "access_notes": "Servizi del Sistema Bibliotecario di Ateneo.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/biblioteche/",
            },
            {
                "place_id": "sala-mostre-centro-congressi",
                "type": "OTHER",
                "name": "Sala Mostre",
                "building_id": "aula-magna",
                "lat": 39.3581044,
                "lng": 16.2256425,
                "description": "Spazio espositivo adiacente all'Aula Magna.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/centro-congressi/",
            }
        ],
        "mensa_buildings": [
            {
                "building_id": "mensa-maisonnettes",
                "name": "Mensa Quartiere Maisonnettes",
                "category": "MENSA",
                "description": "Aperta a pranzo e cena. Pranzo: ore 12:00 - 15:00.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/servizio-mensa/",
            },
            {
                "building_id": "mensa-piazza-vermicelli",
                "name": "Mensa Piazza Vermicelli",
                "category": "MENSA",
                "lat": 39.36761,
                "lng": 16.22529,
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/servizio-mensa/",
            },
        ],
        "building_overrides": [
            {
                "building_id": "aula-magna",
                "name": "Aula Magna",
                "description": "Aula Magna B. Andreatta",
                "source_id": "unical-campus-map",
                "source_url": "https://www.unical.it/campus/visita-il-campus/mappa/",
            }
        ],
        "remove_building_ids": [
            "mensa-maisonnettes-senior",
            "quartiere-monaci",
        ],
        "entity_links": [
            {
                "parent_entity_type": "PLACE",
                "parent_entity_id": "service-quartieri",
                "relation_type": "HAS_CHILD_PLACE",
                "child_entity_type": "PLACE",
                "child_entity_id": "quartiere-maisonnettes",
                "sort_order": 10,
            },
            {
                "parent_entity_type": "PLACE",
                "parent_entity_id": "service-servizio-mensa",
                "relation_type": "HAS_CHILD_BUILDING",
                "child_entity_type": "BUILDING",
                "child_entity_id": "mensa-maisonnettes",
                "sort_order": 20,
            },
            {
                "parent_entity_type": "PLACE",
                "parent_entity_id": "quartiere-maisonnettes",
                "relation_type": "HAS_CHILD_BUILDING",
                "child_entity_type": "BUILDING",
                "child_entity_id": "maisonnettes",
                "sort_order": 30,
            },
            {
                "parent_entity_type": "PLACE",
                "parent_entity_id": "service-centro-congressi",
                "relation_type": "HAS_CHILD_PLACE",
                "child_entity_type": "PLACE",
                "child_entity_id": "sala-mostre-centro-congressi",
                "sort_order": 40,
            },
        ],
    }

    updated_places, updated_buildings, entity_links = apply_service_location_contract(
        places=places,
        buildings=buildings,
        contract=contract,
        verified_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
    )

    places_by_id = {item["place_id"]: item for item in updated_places}
    buildings_by_id = {item["building_id"]: item for item in updated_buildings}
    links_by_id = {item["link_id"]: item for item in entity_links}

    assert "building_id" not in places_by_id["service-quartieri"]
    assert "building_id" not in places_by_id["service-servizio-mensa"]
    assert "building_id" not in places_by_id["service-centro-congressi"]
    assert "building_id" not in places_by_id["service-biblioteche"]
    assert places_by_id["service-biblioteche"]["website_url"] == "https://sba.unical.it/"
    assert places_by_id["service-biblioteche"]["opening_hours"] == (
        "Da lunedì a giovedì 09:00-20:05. Venerdì 09:00-17:00. Sabato chiuso."
    )
    assert places_by_id["quartiere-maisonnettes"]["type"] == "QUARTIERE"
    assert places_by_id["quartiere-maisonnettes"]["lat"] == 39.3555355
    assert places_by_id["quartiere-maisonnettes"]["description"] == "Complesso residenziale del campus."
    assert places_by_id["quartiere-maisonnettes"]["email"] == "mariarosa.spinaiaconis@unical.it"
    assert places_by_id["quartiere-maisonnettes"]["phone"] == "346/3668313"
    assert places_by_id["quartiere-maisonnettes"]["website_url"] == "https://soscr.unical.it/"
    assert places_by_id["quartiere-maisonnettes"]["access_notes"] == "Posti: 519. Servizi: Internet Wi-Fi."
    assert places_by_id["sala-mostre-centro-congressi"]["building_id"] == "aula-magna"
    assert places_by_id["sala-mostre-centro-congressi"]["type"] == "OTHER"

    assert buildings_by_id["mensa-maisonnettes"]["name"] == "Mensa Quartiere Maisonnettes"
    assert buildings_by_id["mensa-maisonnettes"]["category"] == "MENSA"
    assert buildings_by_id["mensa-maisonnettes"]["description"] == (
        "Aperta a pranzo e cena. Pranzo: ore 12:00 - 15:00."
    )
    assert buildings_by_id["mensa-maisonnettes"]["source_id"] == "unical-services"
    assert buildings_by_id["mensa-piazza-vermicelli"]["category"] == "MENSA"
    assert "mensa-maisonnettes-senior" not in buildings_by_id
    assert "quartiere-monaci" not in buildings_by_id

    assert "service-quartieri__has_child_place__quartiere-maisonnettes" in links_by_id
    assert "quartiere-maisonnettes__has_child_building__maisonnettes" in links_by_id
    assert "service-centro-congressi__has_child_place__sala-mostre-centro-congressi" in links_by_id
