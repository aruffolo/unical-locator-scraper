from __future__ import annotations

from unical_scraper.transform.aliases import (
    build_aula_place_aliases,
    build_landmark_aliases,
    build_search_aliases,
)


def test_build_aula_place_aliases_generates_code_variants() -> None:
    aulas = [
        {
            "aula_id": "aula-p2-cubo-30c",
            "place_id": "aula-p2-cubo-30c",
            "name": "Aula P2",
            "room": "P2",
            "short_code": "P2",
        }
    ]
    places = [
        {
            "place_id": "aula-p2-cubo-30c",
            "type": "AULA",
            "name": "Aula P2",
        }
    ]

    aliases = build_aula_place_aliases(aulas=aulas, places=places)
    labels = {alias["label"] for alias in aliases}
    normalized = {alias["normalized"] for alias in aliases}

    assert "Aula P2" in labels
    assert "P2" in labels
    assert "P 2" in labels
    assert "Aula Aula P2" not in labels
    assert "aula-p2" in normalized
    assert "p2" in normalized
    assert all(alias["entity_type"] == "PLACE" for alias in aliases)
    assert all(alias["entity_id"] == "aula-p2-cubo-30c" for alias in aliases)


def test_build_aula_place_aliases_skips_non_aula_places() -> None:
    aulas = [
        {
            "aula_id": "aula-p2-cubo-30c",
            "place_id": "aula-p2-cubo-30c",
            "name": "Aula P2",
            "room": "P2",
            "short_code": "P2",
        }
    ]
    places = [
        {
            "place_id": "aula-p2-cubo-30c",
            "type": "SERVICE",
            "name": "Aula P2",
        }
    ]

    aliases = build_aula_place_aliases(aulas=aulas, places=places)
    assert aliases == []


def test_build_landmark_aliases_only_uses_existing_targets() -> None:
    buildings = [
        {"building_id": "teatro-piccolo"},
        {"building_id": "aula-magna"},
        {"building_id": "cappella-universitaria"},
    ]
    places = [
        {"place_id": "service-centro-congressi"},
        {"place_id": "service-biblioteche"},
    ]

    aliases = build_landmark_aliases(buildings=buildings, places=places)
    by_label = {alias["label"]: (alias["entity_type"], alias["entity_id"]) for alias in aliases}

    assert by_label["PTU"] == ("BUILDING", "teatro-piccolo")
    assert by_label["Aula Magna B. Andreatta"] == ("PLACE", "service-centro-congressi")
    assert by_label["Biblioteca"] == ("PLACE", "service-biblioteche")
    assert by_label["Cappella"] == ("BUILDING", "cappella-universitaria")
    assert "TAU" not in by_label


def test_build_search_aliases_merges_aulas_and_landmarks() -> None:
    aulas = [
        {
            "aula_id": "aula-p2-cubo-30c",
            "place_id": "aula-p2-cubo-30c",
            "name": "Aula P2",
            "room": "P2",
            "short_code": "P2",
        }
    ]
    places = [
        {"place_id": "aula-p2-cubo-30c", "type": "AULA", "name": "Aula P2"},
        {"place_id": "service-centro-congressi", "type": "SERVICE", "name": "Centro Congressi"},
    ]
    buildings = [{"building_id": "teatro-piccolo"}]

    aliases = build_search_aliases(aulas=aulas, places=places, buildings=buildings)
    labels = {alias["label"] for alias in aliases}

    assert "P2" in labels
    assert "PTU" in labels
    assert "Centro Congressi" in labels


def test_build_search_aliases_preserves_martenson_spelling_alias() -> None:
    aliases = build_search_aliases(
        aulas=[],
        places=[],
        buildings=[
            {
                "building_id": "mensa-martenson",
                "name": "Mensa Quartiere Martensson",
            }
        ],
    )

    by_label = {alias["label"]: alias["entity_id"] for alias in aliases}
    assert by_label["Mensa Martenson"] == "mensa-martenson"
    assert by_label["Mensa Quartiere Martenson"] == "mensa-martenson"
