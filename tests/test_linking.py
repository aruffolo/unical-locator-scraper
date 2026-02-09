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
