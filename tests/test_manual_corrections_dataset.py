from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "normalized"

LOCKED_MIN_COUNTS = {
    "aliases.json": 1393,
    "aulas.json": 517,
    "building_entrances.json": 0,
    "buildings.json": 147,
    "departments.json": 14,
    "entity_links.json": 39,
    "faqs.json": 0,
    "glossary.json": 0,
    "people.json": 4156,
    "places.json": 901,
    "sources.json": 5,
}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_dataset(name: str) -> list[dict[str, Any]]:
    payload = _load_json(DATA_DIR / name)
    assert isinstance(payload, list)
    return [entry for entry in payload if isinstance(entry, dict)]


def _by_id(rows: list[dict[str, Any]], id_field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw_id = row.get(id_field)
        if isinstance(raw_id, str) and raw_id:
            result[raw_id] = row
    return result


def test_required_entities_are_present_in_canonical_datasets() -> None:
    buildings = _by_id(_load_dataset("buildings.json"), "building_id")
    places = _by_id(_load_dataset("places.json"), "place_id")
    people = _by_id(_load_dataset("people.json"), "person_id")
    entity_links = _by_id(_load_dataset("entity_links.json"), "link_id")

    assert "cappella-universitaria" in buildings
    assert "cubo-20" in buildings
    assert "mensa-piazza-vermicelli" in buildings
    assert "poli-bistrot-polifunzionale" in buildings
    assert "auditorium-teatro-grande" in buildings
    assert "teatro-piccolo" in buildings
    assert "office-ufficio-cubo-0-c-primo-piano" in places
    assert "service-centro-sportivo" in places
    assert "service-quartieri" in places
    assert "service-servizio-mensa" in places
    assert "service-centro-congressi" in places
    assert "service-teatri-e-cinema" in places
    assert "service-biblioteche" in places
    assert "service-sistema-museale" in places
    assert "service-servizio-foresteria" in places
    assert "service-emergenze-e-assistenza-sanitaria" not in places
    assert "quartiere-chiodo" in places
    assert "quartiere-san-gennaro" in places
    assert "sala-mostre-centro-congressi" in places
    assert "aula-magna-centro-congressi" in places
    assert "aula-u-caldora-centro-congressi" in places
    assert "university-club" in places
    assert "cinema-unical" in places
    assert "biblioteca-bau" in places
    assert "biblioteca-tarantelli" in places
    assert "biblioteca-bats" in places
    assert "service-musnob" in places
    assert "service-rimuseum" in places
    assert "service-miai" in places
    assert "service-orto-botanico" in places
    assert "service-paleontologia" in places
    assert "service-zoologia" in places
    assert "service-mineralogia-e-petrografia" in places
    assert "residenza-socrates" in places
    assert "polo-infanzia" in places
    assert "office-ufficio-cubo-4c-piano-3" in places
    assert "francesco-scarcello" in people
    assert (
        "service-quartieri__has_child_place__quartiere-chiodo" in entity_links
    )
    assert (
        "service-servizio-mensa__has_child_building__mensa-piazza-vermicelli"
        in entity_links
    )
    assert "service-centro-congressi__has_child_place__sala-mostre-centro-congressi" in entity_links
    assert "service-teatri-e-cinema__has_child_place__cinema-unical" in entity_links
    assert "service-biblioteche__has_child_place__biblioteca-bau" in entity_links
    assert "service-sistema-museale__has_child_place__service-musnob" in entity_links
    assert "service-servizio-foresteria__has_child_place__residenza-socrates" in entity_links
    assert "service-polo-infanzia__has_child_place__polo-infanzia" not in entity_links


def test_known_manual_wave_fixes_are_preserved() -> None:
    buildings = _by_id(_load_dataset("buildings.json"), "building_id")
    places = _by_id(_load_dataset("places.json"), "place_id")
    people = _by_id(_load_dataset("people.json"), "person_id")

    cappella = buildings["cappella-universitaria"]
    # Wave 01 safe-drop family: map boilerplate removed from building description.
    assert cappella.get("description") is None

    cubo_20 = buildings["cubo-20"]
    assert cubo_20.get("description") == "Dipartimento di Lingue e Scienze dell'Educazione"
    assert "Link portale:" not in str(cubo_20.get("description"))

    office_0c = places["office-ufficio-cubo-0-c-primo-piano"]
    assert office_0c.get("office_reference_text") == "Cubo 0/C Primo piano"
    assert "Office references:" not in str(office_0c.get("description"))

    service_cus = places["service-centro-sportivo"]
    assert service_cus.get("website_url") == "https://my.unical.it/"
    assert service_cus.get("access_notes") is None

    office_4c = places["office-ufficio-cubo-4c-piano-3"]
    assert isinstance(office_4c.get("meeting_url"), str)
    assert office_4c.get("meeting_code") == "6wlha6g"
    assert "teams.microsoft.com" not in str(office_4c.get("opening_hours")).casefold()

    scarcello = people["francesco-scarcello"]
    assert scarcello.get("office_reference_text") == "Cubo 41C Piano 3"
    assert "Office references:" not in str(scarcello.get("notes"))


def test_grouped_service_location_wave_is_preserved() -> None:
    buildings = _by_id(_load_dataset("buildings.json"), "building_id")
    places = _by_id(_load_dataset("places.json"), "place_id")
    entity_links = _by_id(_load_dataset("entity_links.json"), "link_id")

    quartieri = places["service-quartieri"]
    assert quartieri.get("building_id") is None
    assert quartieri.get("website_url") == "https://my.unical.it/"

    servizio_mensa = places["service-servizio-mensa"]
    assert servizio_mensa.get("building_id") is None
    assert servizio_mensa.get("opening_hours") == "Orari disponibili sulla pagina sorgente"

    martensson = buildings["mensa-martenson"]
    assert martensson.get("name") == "Mensa Quartiere Martensson"
    assert martensson.get("category") == "MENSA"
    assert "Pranzo: ore 12:00 - 15:00." in str(martensson.get("description"))
    assert "Cena: ore 19:00 - 21:30" in str(martensson.get("description"))
    assert martensson.get("source_url") == (
        "https://www.unical.it/campus/vivere-il-campus/servizio-mensa/"
    )

    piazza_vermicelli = buildings["mensa-piazza-vermicelli"]
    assert piazza_vermicelli.get("category") == "MENSA"
    assert piazza_vermicelli.get("description") == (
        "Aperta dal lunedi al venerdi. Pranzo: ore 12:00 - 15:00."
    )

    assert "mensa-maisonnettes-senior" not in buildings
    assert "mensa-martenson-ingresso" not in buildings
    assert "mensa-studenti-ingresso" not in buildings
    assert "quartiere-blocco-11-e-12" not in buildings
    assert "quartiere-monaci" not in buildings
    assert "quartiere-nervoso" not in buildings

    quartiere_monaci = places["quartiere-monaci"]
    assert quartiere_monaci.get("type") == "QUARTIERE"
    assert quartiere_monaci.get("description") is not None
    assert quartiere_monaci.get("email") == "roberto.bartucci@unical.it"
    assert quartiere_monaci.get("phone") == "338/2518197"
    assert quartiere_monaci.get("website_url") == "https://soscr.unical.it/"
    assert "Posti: 202." in str(quartiere_monaci.get("access_notes"))
    assert "Spazi comuni:" in str(quartiere_monaci.get("access_notes"))
    assert (
        "quartiere-monaci__has_child_building__quartiere-monaci" not in entity_links
    )
    assert (
        "quartiere-nervoso__has_child_building__quartiere-nervoso" not in entity_links
    )


def test_broader_grouped_hub_wave_is_preserved() -> None:
    buildings = _by_id(_load_dataset("buildings.json"), "building_id")
    places = _by_id(_load_dataset("places.json"), "place_id")
    entity_links = _by_id(_load_dataset("entity_links.json"), "link_id")

    centro_congressi = places["service-centro-congressi"]
    assert centro_congressi.get("building_id") is None
    assert centro_congressi.get("opening_hours") is None
    assert centro_congressi.get("website_url") is None
    assert "Marcella Giulia Lorenzi" in str(centro_congressi.get("access_notes"))

    teatri = places["service-teatri-e-cinema"]
    assert teatri.get("building_id") is None
    assert teatri.get("opening_hours") is None
    assert teatri.get("website_url") is None
    assert teatri.get("email") == "dir.cams@unical.it"

    aula_magna_congressi = places["aula-magna-centro-congressi"]
    assert aula_magna_congressi.get("type") == "OTHER"
    assert aula_magna_congressi.get("building_id") == "aula-magna"
    assert "660 posti" in str(aula_magna_congressi.get("description"))

    aula_caldora_congressi = places["aula-u-caldora-centro-congressi"]
    assert aula_caldora_congressi.get("type") == "OTHER"
    assert aula_caldora_congressi.get("building_id") == "centro-radiotelevisivo"
    assert "250 persone" in str(aula_caldora_congressi.get("description"))

    sala_mostre = places["sala-mostre-centro-congressi"]
    assert sala_mostre.get("type") == "OTHER"
    assert sala_mostre.get("building_id") == "aula-magna"
    assert "Adiacente l'Aula Magna" in str(sala_mostre.get("description"))

    university_club = places["university-club"]
    assert university_club.get("type") == "OTHER"
    assert university_club.get("building_id") == "cubo-24b"
    assert "80 posti a sedere" in str(university_club.get("description"))

    sala_a = places["sala-a-centro-congressi"]
    assert "50 posti" in str(sala_a.get("description"))

    cinema_unical = places["cinema-unical"]
    assert cinema_unical.get("type") == "OTHER"
    assert cinema_unical.get("building_id") == "auditorium-teatro-grande"
    assert cinema_unical.get("website_url") == "https://cosenzacinema.it/programmazione-sale-unical/"
    assert cinema_unical.get("email") == "dir.cams@unical.it"
    assert "dotato di 2 sale" in str(cinema_unical.get("description"))
    assert "programmazione serale" in str(cinema_unical.get("access_notes"))

    tau = buildings["auditorium-teatro-grande"]
    assert "Teatro Auditorium Unical (TAU)" in str(tau.get("description"))
    assert "550 posti" in str(tau.get("description"))

    ptu = buildings["teatro-piccolo"]
    assert "Piccolo Teatro Unical (PTU)" in str(ptu.get("description"))
    assert "300 posti" in str(ptu.get("description"))

    biblioteca_bau = places["biblioteca-bau"]
    assert biblioteca_bau.get("type") == "LIBRARY"
    assert biblioteca_bau.get("website_url") == "https://bau.unical.it/"
    assert "istituita nel 1987" in str(biblioteca_bau.get("description"))
    assert biblioteca_bau.get("opening_hours") == (
        "Da lunedì a giovedì 09:00-20:05. Venerdì 09:00-17:00. Sabato chiuso."
    )
    assert "https://sba.unical.it/" in str(biblioteca_bau.get("access_notes"))

    biblioteca_tarantelli = places["biblioteca-tarantelli"]
    assert biblioteca_tarantelli.get("type") == "LIBRARY"
    assert biblioteca_tarantelli.get("website_url") == "http://tar.unical.it/"
    assert "nata nel 1981" in str(biblioteca_tarantelli.get("description"))
    assert biblioteca_tarantelli.get("opening_hours") == (
        "Da lunedì a giovedì 09:00-20:05. Venerdì 09:00-17:00. Sabato chiuso."
    )

    biblioteca_bats = places["biblioteca-bats"]
    assert biblioteca_bats.get("type") == "LIBRARY"
    assert biblioteca_bats.get("website_url") == "http://bats.unical.it/"
    assert "nata nel 1999" in str(biblioteca_bats.get("description"))
    assert biblioteca_bats.get("opening_hours") == (
        "Da lunedì a giovedì 09:00-20:05. Venerdì 09:00-17:00. Sabato chiuso."
    )
    assert "https://ticket.unical.it/tickets/new/15/570/" in str(
        biblioteca_bats.get("access_notes")
    )

    biblioteche = places["service-biblioteche"]
    assert biblioteche.get("building_id") is None
    assert biblioteche.get("website_url") == "https://sba.unical.it/"
    assert biblioteche.get("opening_hours") == (
        "Da lunedì a giovedì 09:00-20:05. Venerdì 09:00-17:00. Sabato chiuso."
    )
    assert "Sistema Bibliotecario di Ateneo" in str(biblioteche.get("access_notes"))

    assert "service-centro-congressi__has_child_place__aula-magna-centro-congressi" in entity_links
    assert (
        "service-centro-congressi__has_child_place__aula-u-caldora-centro-congressi"
        in entity_links
    )
    assert "service-centro-congressi__has_child_place__university-club" in entity_links
    assert "service-teatri-e-cinema__has_child_building__auditorium-teatro-grande" in entity_links
    assert "service-teatri-e-cinema__has_child_building__teatro-piccolo" in entity_links
    assert "cinema-unical__has_child_building__auditorium-teatro-grande" in entity_links
    assert "service-biblioteche__has_child_place__biblioteca-bats" in entity_links


def test_museale_foresteria_polo_wave_is_preserved() -> None:
    places = _by_id(_load_dataset("places.json"), "place_id")
    entity_links = _by_id(_load_dataset("entity_links.json"), "link_id")

    sistema_museale = places["service-sistema-museale"]
    assert sistema_museale.get("type") == "SERVICE"
    assert sistema_museale.get("building_id") is None
    assert "SiMU" in str(sistema_museale.get("description"))
    assert "visite, percorsi e laboratori" in str(sistema_museale.get("access_notes"))

    musnob = places["service-musnob"]
    assert musnob.get("type") == "OTHER"
    assert musnob.get("name") == "MuSNOB"
    assert musnob.get("website_url") is None
    assert musnob.get("opening_hours") == "Lunedì-venerdì 09:00-13:00."
    assert musnob.get("phone") == "0984 493089"
    assert musnob.get("email") == "infomusei@unical.it; musnob@unical.it"
    assert "appuntamenti e visite tematiche" in str(musnob.get("access_notes")).lower()

    rimuseum = places["service-rimuseum"]
    assert rimuseum.get("type") == "OTHER"
    assert rimuseum.get("name") == "RiMuseum"
    assert rimuseum.get("opening_hours") == (
        "Lunedì-giovedì 09:00-13:00 / 14:00-17:00. "
        "Venerdì 09:00-13:00, pomeriggio apertura su prenotazione. "
        "Sabato e domenica apertura su prenotazione."
    )
    assert rimuseum.get("phone") == "0984 465353"
    assert rimuseum.get("email") == "infomusei@unical.it"
    assert "Via Cavour, 1" in str(rimuseum.get("access_notes"))

    miai = places["service-miai"]
    assert miai.get("type") == "OTHER"
    assert miai.get("name") == "MIAI"

    orto = places["service-orto-botanico"]
    assert orto.get("type") == "OTHER"
    assert orto.get("building_id") == "orto-botanico"
    assert orto.get("opening_hours") == "Lunedì-venerdì 09:00-13:00."
    assert orto.get("phone") == "0984 493089"
    assert orto.get("email") == "infomusei@unical.it"

    paleontologia = places["service-paleontologia"]
    assert paleontologia.get("type") == "OTHER"
    assert paleontologia.get("opening_hours") == "Lunedì-venerdì 09:00-13:00."
    assert paleontologia.get("phone") == "0984 493685"
    assert paleontologia.get("email") == "infomusei@unical.it; anna.rao@unical.it"

    zoologia = places["service-zoologia"]
    assert zoologia.get("type") == "OTHER"
    assert zoologia.get("opening_hours") == "Lunedì-venerdì 09:00-13:00."
    assert zoologia.get("email") == "infomusei@unical.it; antonio.mazzei@unical.it"

    mineralogia = places["service-mineralogia-e-petrografia"]
    assert mineralogia.get("type") == "OTHER"
    assert mineralogia.get("phone") == "0984 493588-3704"
    assert mineralogia.get("email") == "andrea.bloise@unical.it"

    foresteria = places["service-servizio-foresteria"]
    assert foresteria.get("building_id") is None
    assert foresteria.get("website_url") == "https://soscr.unical.it/"
    assert "monolocale € 280,00" in str(foresteria.get("access_notes"))

    socrates = places["residenza-socrates"]
    assert socrates.get("type") == "OTHER"
    assert socrates.get("website_url") == "https://www.ialbergo.it/booking/dispob.aspx?id=570"
    assert socrates.get("lat") == 39.3639597
    assert socrates.get("lng") == 16.2234723
    assert "servizio di tipo alberghiero" in str(socrates.get("description"))

    assert "service-polo-infanzia" not in places

    polo_place = places["polo-infanzia"]
    assert polo_place.get("type") == "OTHER"
    assert polo_place.get("building_id") == "auditorium-teatro-grande"
    assert polo_place.get("lat") == 39.3639597
    assert polo_place.get("lng") == 16.2234723
    assert polo_place.get("email") == "commissionepoloinfanzia@unical.it"
    assert "Asilo nido, Scuola d'Infanzia e mensa interna" in str(polo_place.get("description"))
    assert "Delegato: Dott. Mario Ferraro." in str(polo_place.get("access_notes"))
    assert "Piazza Vermicelli - 87036 Rende (CS)." in str(polo_place.get("access_notes"))

    assert "service-sistema-museale__has_child_place__service-musnob" in entity_links
    assert "service-sistema-museale__has_child_place__service-rimuseum" in entity_links
    assert "service-sistema-museale__has_child_place__service-miai" in entity_links
    assert "service-musnob__has_child_place__service-orto-botanico" in entity_links
    assert "service-musnob__has_child_place__service-paleontologia" in entity_links
    assert "service-musnob__has_child_place__service-zoologia" in entity_links
    assert "service-musnob__has_child_place__service-mineralogia-e-petrografia" in entity_links
    assert "service-servizio-foresteria__has_child_place__residenza-socrates" in entity_links
    assert "service-polo-infanzia__has_child_place__polo-infanzia" not in entity_links
    assert "polo-infanzia__has_child_building__auditorium-teatro-grande" in entity_links


def test_centro_sanitario_enrichment_wave_is_preserved() -> None:
    places = _by_id(_load_dataset("places.json"), "place_id")

    centro_sanitario = places["service-centro-sanitario"]
    assert centro_sanitario.get("type") == "SERVICE"
    assert centro_sanitario.get("building_id") == "centro-sanitario"
    assert centro_sanitario.get("website_url") is None
    assert "presidio assistenziale di riferimento" in str(
        centro_sanitario.get("description")
    ).lower()
    assert centro_sanitario.get("opening_hours") == (
        "Laboratorio prelievi e ritiro referti: lunedì-venerdì 08:15-10:00. "
        "Consultorio familiare: lunedì-venerdì 09:00-13:00; "
        "martedì e giovedì 15:30-17:00. "
        "Continuità assistenziale / Guardia Medica: 24h/24h. "
        "Emergenza 118: 24h/24h."
    )
    assert centro_sanitario.get("email") == (
        "centrosanitario@unical.it; 118cosenza@tiscali.it; "
        "centraleoperativa118@pec.asp.cosenza.it"
    )
    assert centro_sanitario.get("phone") == (
        "0984 496200; 0984 496215; 0984 496202; 0984 402518; 0984/37356"
    )
    assert "Cubo 34B - Via Pietro Bucci" in str(centro_sanitario.get("access_notes"))
    assert "Prenotazioni esami tramite ESSE3." in str(
        centro_sanitario.get("access_notes")
    )
    assert "service-emergenze-e-assistenza-sanitaria" not in places


def test_dataset_contract_counts_match_files_and_locked_minimums() -> None:
    contract = _load_json(DATA_DIR / "dataset_contract.json")
    assert isinstance(contract, dict)
    datasets = contract.get("datasets")
    assert isinstance(datasets, list)

    contract_counts: dict[str, int] = {}
    for row in datasets:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        records = row.get("records")
        if isinstance(name, str) and isinstance(records, int):
            contract_counts[name] = records

    assert contract_counts.keys() >= LOCKED_MIN_COUNTS.keys()

    for dataset_name, minimum_count in LOCKED_MIN_COUNTS.items():
        dataset_rows = _load_dataset(dataset_name)
        actual_count = len(dataset_rows)
        assert actual_count >= minimum_count
        assert contract_counts[dataset_name] == actual_count
