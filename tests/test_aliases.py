from __future__ import annotations

from unical_scraper.transform.aliases import build_aula_place_aliases


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
