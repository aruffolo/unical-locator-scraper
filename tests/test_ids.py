from unical_scraper.transform.ids import (
    make_department_id,
    make_person_id,
    make_place_id,
    stable_slug,
)


def test_stable_slug_handles_accents_and_spaces() -> None:
    assert stable_slug("Dipartimento di Matematica e Informatica") == "dipartimento-di-matematica-e-informatica"
    assert stable_slug("Cubo 18B") == "cubo-18b"


def test_make_person_id_uses_surname_name_order() -> None:
    assert make_person_id("Francesco Scarcellò") == "scarcello-francesco"


def test_make_person_id_falls_back_to_email() -> None:
    assert make_person_id("", email="mario.rossi@unical.it") == "mario-rossi"


def test_make_department_id() -> None:
    assert make_department_id("DIMES") == "dimes"


def test_make_place_id() -> None:
    assert make_place_id("Segreteria Studenti", "SECRETARY") == "secretary-segreteria-studenti"
