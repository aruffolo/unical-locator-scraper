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
            "opening_hours": "placeholder",
            "website_url": "https://my.unical.it/",
        },
        {
            "place_id": "service-biblioteche",
            "type": "SERVICE",
            "name": "Biblioteche",
            "building_id": "cubo-libro",
        },
        {
            "place_id": "service-servizio-foresteria",
            "type": "SERVICE",
            "name": "Servizio Foresteria",
            "building_id": "uffici-centro-residenziale-e-area-didattica",
        },
        {
            "place_id": "service-polo-infanzia",
            "type": "SERVICE",
            "name": "Polo d'Infanzia",
            "building_id": "auditorium-teatro-grande",
            "website_url": "https://my.unical.it/",
        },
        {
            "place_id": "service-musnob",
            "type": "SERVICE",
            "name": "Musnob",
            "website_url": "https://my.unical.it/",
        },
    ]
    buildings = [
        {"building_id": "mensa-maisonnettes", "name": "Mensa Maisonnettes"},
        {"building_id": "mensa-martenson", "name": "Mensa Martenson"},
        {"building_id": "mensa-maisonnettes-senior", "name": "Mensa Maisonnettes Senior"},
        {"building_id": "quartiere-monaci", "name": "Quartiere Monaci"},
        {"building_id": "maisonnettes", "name": "Maisonnettes"},
        {"building_id": "aula-magna", "name": "Aula Magna"},
        {"building_id": "auditorium-teatro-grande", "name": "Auditorium Teatro Grande"},
    ]
    contract = {
        "clear_overview_building_ids": [
            "service-quartieri",
            "service-servizio-mensa",
            "service-centro-congressi",
            "service-biblioteche",
            "service-servizio-foresteria",
            "service-polo-infanzia",
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
                "place_id": "service-sistema-museale",
                "type": "SERVICE",
                "name": "Sistema Museale",
                "description": "Racconta collezioni e ricerca dei musei dell'Ateneo.",
                "access_notes": "Visite e laboratori per il territorio.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/sistema-museale/",
            },
            {
                "place_id": "service-musnob",
                "type": "OTHER",
                "name": "MuSNOB",
                "clear_fields": ["website_url"],
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/sistema-museale/musnob/",
            },
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
                "place_id": "service-centro-congressi",
                "type": "SERVICE",
                "name": "Centro Congressi",
                "clear_fields": ["opening_hours", "website_url"],
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/centro-congressi/",
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
            },
            {
                "place_id": "service-servizio-foresteria",
                "type": "SERVICE",
                "name": "Servizio Foresteria",
                "clear_building_id": True,
                "website_url": "https://soscr.unical.it/",
                "access_notes": "Richiesta foresteria su soscr.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/servizio-foresteria/",
            },
            {
                "place_id": "residenza-socrates",
                "type": "OTHER",
                "name": "Residenza Socrates",
                "website_url": "https://www.ialbergo.it/booking/dispob.aspx?id=570",
                "access_notes": "Servizio alberghiero.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/servizio-foresteria/",
            },
            {
                "place_id": "service-polo-infanzia",
                "type": "SERVICE",
                "name": "Polo d'Infanzia",
                "clear_building_id": True,
                "clear_fields": ["website_url"],
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/polo-infanzia/",
            },
            {
                "place_id": "polo-infanzia",
                "type": "OTHER",
                "name": "Polo d'Infanzia",
                "building_id": "auditorium-teatro-grande",
                "lat": 39.3639597,
                "lng": 16.2234723,
                "description": "Nido, scuola d'infanzia e mensa interna.",
                "source_id": "unical-services",
                "source_url": "https://www.unical.it/campus/vivere-il-campus/polo-infanzia/",
            },
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
                "parent_entity_id": "service-sistema-museale",
                "relation_type": "HAS_CHILD_PLACE",
                "child_entity_type": "PLACE",
                "child_entity_id": "service-musnob",
                "sort_order": 5,
            },
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
            {
                "parent_entity_type": "PLACE",
                "parent_entity_id": "service-servizio-foresteria",
                "relation_type": "HAS_CHILD_PLACE",
                "child_entity_type": "PLACE",
                "child_entity_id": "residenza-socrates",
                "sort_order": 50,
            },
            {
                "parent_entity_type": "PLACE",
                "parent_entity_id": "service-polo-infanzia",
                "relation_type": "HAS_CHILD_PLACE",
                "child_entity_type": "PLACE",
                "child_entity_id": "polo-infanzia",
                "sort_order": 60,
            },
            {
                "parent_entity_type": "PLACE",
                "parent_entity_id": "polo-infanzia",
                "relation_type": "HAS_CHILD_BUILDING",
                "child_entity_type": "BUILDING",
                "child_entity_id": "auditorium-teatro-grande",
                "sort_order": 70,
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
    assert "opening_hours" not in places_by_id["service-centro-congressi"]
    assert "website_url" not in places_by_id["service-centro-congressi"]
    assert "building_id" not in places_by_id["service-biblioteche"]
    assert places_by_id["service-sistema-museale"]["type"] == "SERVICE"
    assert places_by_id["service-musnob"]["type"] == "OTHER"
    assert places_by_id["service-musnob"]["name"] == "MuSNOB"
    assert "website_url" not in places_by_id["service-musnob"]
    assert places_by_id["service-biblioteche"]["website_url"] == "https://sba.unical.it/"
    assert places_by_id["service-biblioteche"]["opening_hours"] == (
        "Da lunedì a giovedì 09:00-20:05. Venerdì 09:00-17:00. Sabato chiuso."
    )
    assert "building_id" not in places_by_id["service-servizio-foresteria"]
    assert places_by_id["service-servizio-foresteria"]["website_url"] == "https://soscr.unical.it/"
    assert "building_id" not in places_by_id["service-polo-infanzia"]
    assert "website_url" not in places_by_id["service-polo-infanzia"]
    assert places_by_id["residenza-socrates"]["type"] == "OTHER"
    assert places_by_id["polo-infanzia"]["building_id"] == "auditorium-teatro-grande"
    assert places_by_id["polo-infanzia"]["lat"] == 39.3639597
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
    assert "service-sistema-museale__has_child_place__service-musnob" in links_by_id
    assert "quartiere-maisonnettes__has_child_building__maisonnettes" in links_by_id
    assert "service-centro-congressi__has_child_place__sala-mostre-centro-congressi" in links_by_id
    assert "service-servizio-foresteria__has_child_place__residenza-socrates" in links_by_id
    assert "service-polo-infanzia__has_child_place__polo-infanzia" in links_by_id
    assert "polo-infanzia__has_child_building__auditorium-teatro-grande" in links_by_id
