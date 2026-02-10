from __future__ import annotations

import json

from unical_scraper.extract.aulas import crawl_aulas


class FakeHttpClient:
    def __init__(
        self,
        pages: dict[str, str],
        post_pages: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self._pages = pages
        self._post_pages = post_pages or {}

    def get_text(self, url: str) -> str:
        return self._pages[url]

    def post_json(self, url: str, payload: dict[str, object]) -> str:
        key = (url, json.dumps(payload, sort_keys=True))
        return self._post_pages[key]


def test_crawl_aulas_extracts_direct_markers_and_floor_mentions() -> None:
    base_url = "https://www.unical.it/campus/visita-il-campus/mappa/"
    kml_url = "https://www.google.com/maps/d/kml?mid=test-mid&forcekml=1"
    pages = {
        base_url: """
            <html><body>
              <iframe src="https://www.google.com/maps/d/embed?mid=test-mid&amp;ehbc=2E312F"></iframe>
            </body></html>
        """,
        kml_url: """
            <?xml version="1.0" encoding="UTF-8"?>
            <kml xmlns="http://www.opengis.net/kml/2.2">
              <Document>
                <Folder>
                  <name>Strutture, edifici, aule ..</name>
                  <Placemark>
                    <name>Cubo 40C - DiMat</name>
                    <description><![CDATA[
                      Descrizione: didattica
                      Piano Terra: Aula A G
                      Primo piano: Sala Stampa
                    ]]></description>
                    <Point><coordinates>16.2266846,39.3605961,0</coordinates></Point>
                  </Placemark>
                  <Placemark>
                    <name>Aula Magna - Convegno Società Italiana di Fisica</name>
                    <Point><coordinates>16.2258276,39.3583149,0</coordinates></Point>
                  </Placemark>
                  <Placemark>
                    <name>Aula Magna</name>
                    <Point><coordinates>16.2258277,39.3583150,0</coordinates></Point>
                  </Placemark>
                </Folder>
              </Document>
            </kml>
        """,
    }

    aulas = crawl_aulas(base_url=base_url, client=FakeHttpClient(pages))
    names = {item.name for item in aulas}

    assert "Aula A G" in names
    assert "Aula Magna" in names
    assert "Aula Magna - Convegno Società Italiana di Fisica" not in names

    aula_ag = next(item for item in aulas if item.name == "Aula A G")
    assert aula_ag.floor == "Piano Terra"
    assert aula_ag.short_code == "AG"
    assert aula_ag.building_hint == "Cubo 40C"


def test_crawl_aulas_ignores_non_aula_markers() -> None:
    base_url = "https://www.unical.it/campus/visita-il-campus/mappa/"
    kml_url = "https://www.google.com/maps/d/kml?mid=test-mid&forcekml=1"
    pages = {
        base_url: """
            <html><body>
              <iframe src="https://www.google.com/maps/d/embed?mid=test-mid&amp;ehbc=2E312F"></iframe>
            </body></html>
        """,
        kml_url: """
            <?xml version="1.0" encoding="UTF-8"?>
            <kml xmlns="http://www.opengis.net/kml/2.2">
              <Document>
                <Folder>
                  <name>Strutture, edifici, aule ..</name>
                  <Placemark>
                    <name>Cubo 18B - DiCES</name>
                    <description><![CDATA[Descrizione: edificio didattico]]></description>
                    <Point><coordinates>16.2266846,39.3605961,0</coordinates></Point>
                  </Placemark>
                  <Placemark>
                    <name>P2 - Polifunzionale Ovest</name>
                    <Point><coordinates>16.2260000,39.3600000,0</coordinates></Point>
                  </Placemark>
                </Folder>
              </Document>
            </kml>
        """,
    }

    aulas = crawl_aulas(base_url=base_url, client=FakeHttpClient(pages))

    assert aulas == []


def test_crawl_aulas_merges_department_and_planner_sources() -> None:
    base_url = "https://www.unical.it/campus/visita-il-campus/mappa/"
    department_url = "https://department.example/strutture/"
    planner_base_url = "https://planner.example"

    pages = {
        base_url: "<html><body>No map iframe</body></html>",
        department_url: """
            <html><body>
              <table>
                <tr><th>Aula</th><th>Cubo</th><th>Capienza</th></tr>
                <tr><td>P2</td><td>Cubo 30C Piano II</td><td>120</td></tr>
                <tr><td>Studio Docente</td><td>Cubo 30C Piano II</td></tr>
              </table>
            </body></html>
        """,
        f"{planner_base_url}/api/Edifici/getPerAutoCompletePublic?lookupFields=codice&limit=100": """
            [
              {"id": "ed1", "codice": "ED_001", "descrizione": "Cubo 31B"},
              {"id": "ed2", "codice": "ED_002", "descrizione": "Cubo 30C"}
            ]
        """,
        f"{planner_base_url}/api/Aule/getPerAutoCompletePublic?lookupFields=codice&limit=100": """
            [
              {"id": "a1", "codice": "AU_001", "descrizione": "Aula CLA"},
              {"id": "a2", "codice": "AU_999", "descrizione": "Studio Docente"},
              {"id": "a3", "codice": "AU_777", "descrizione": "P5"}
            ]
        """,
        f"{planner_base_url}/api/Aule/getByIdPublic?id=a1": """
            {"id": "a1", "codice": "AU_001", "descrizione": "Aula CLA", "edificioId": "ed1"}
        """,
        f"{planner_base_url}/api/Aule/getByIdPublic?id=a2": """
            {"id": "a2", "codice": "AU_999", "descrizione": "Studio Docente", "edificioId": "ed1"}
        """,
        f"{planner_base_url}/api/Aule/getByIdPublic?id=a3": """
            {"id": "a3", "codice": "AU_777", "descrizione": "P5", "edificioId": "ed2"}
        """,
        f"{planner_base_url}/api/Impegni/getImpegniPublic?dataInizio=2020-01-01&dataFine=2030-12-31&limit=20000": """
            [
              {
                "id": "imp-1",
                "aule": [
                  {
                    "id": "room-imp",
                    "codice": "AU_1234",
                    "descrizione": "MT 10",
                    "edificioId": "ed2",
                    "edificio": {"id": "ed2", "descrizione": "Cubo 30C"}
                  },
                  {
                    "id": "room-imp2",
                    "codice": "AU_9999",
                    "descrizione": "Sala Consiglio",
                    "edificioId": "ed1",
                    "edificio": {"id": "ed1", "descrizione": "Cubo 31B"}
                  },
                  {
                    "id": "room-imp3",
                    "codice": "AU_8888",
                    "descrizione": "Laboratorio Informatica 1",
                    "edificioId": "ed1",
                    "edificio": {"id": "ed1", "descrizione": "Cubo 31B"}
                  },
                  {
                    "id": "room-imp4",
                    "codice": "AU_7777",
                    "descrizione": "Vibora Padel Club",
                    "edificioId": "ed1",
                    "edificio": {"id": "ed1", "descrizione": "Cubo 31B"}
                  }
                ]
              }
            ]
        """,
    }
    post_pages = {
        (
            f"{planner_base_url}/api/Aule/getAulePerCalendarioPubblico",
            json.dumps(
                {
                    "linkCalendarioId": "62306d204f9d7f00e457a21c",
                    "clienteId": "5de6319d4414ab02f80b613a",
                },
                sort_keys=True,
            ),
        ): """
            [
              {
                "id": "room-link",
                "codice": "AU_5555",
                "descrizione": "Aula T1",
                "edificioId": "ed1"
              }
            ]
        """,
    }
    pages["https://ctc.unical.it/didattica/iscriversi-studiare-laurearsi/frequentare-i-corsi/"] = """
        <html><body>
          <a href="https://unical.prod.up.cineca.it/calendarioPubblico/linkCalendarioId=62306d204f9d7f00e457a21c">Orario</a>
        </body></html>
    """

    aulas = crawl_aulas(
        base_url=base_url,
        client=FakeHttpClient(pages, post_pages=post_pages),
        department_urls=(department_url,),
        planner_base_url=planner_base_url,
        planner_calendar_discovery_urls=(
            "https://ctc.unical.it/didattica/iscriversi-studiare-laurearsi/frequentare-i-corsi/",
        ),
    )

    names = {item.name for item in aulas}
    assert "Aula P2" in names
    assert "Aula CLA" in names
    assert "Aula P5" in names
    assert "Aula T1" in names
    assert "Aula MT10" in names
    assert "Laboratorio Informatica 1" in names
    assert "Studio Docente" not in names
    assert "Aula Sala Consiglio" not in names
    assert "Vibora Padel Club" not in names

    aula_p2 = next(item for item in aulas if item.name == "Aula P2")
    assert aula_p2.floor == "Secondo piano"
    assert aula_p2.building_hint == "Cubo 30C"
    assert aula_p2.capacity == 120


def test_crawl_aulas_parses_department_strutture_capacity_and_floor_variants() -> None:
    base_url = "https://www.unical.it/campus/visita-il-campus/mappa/"
    department_url = "https://dices.unical.it/dipartimento/organizzazione/strutture/"
    pages = {
        base_url: "<html><body>No map iframe</body></html>",
        department_url: """
            <html><body>
              <table>
                <tr><th>Aula</th><th>Cubo</th><th>Piano/liv.</th><th>Posti</th></tr>
                <tr><td>Apollo</td><td>18B</td><td>Piano 0</td><td>129</td></tr>
                <tr><td>A Ling.</td><td>20B</td><td>Piano 0</td><td>63</td></tr>
              </table>
            </body></html>
        """,
        "https://planner.example/api/Edifici/getPerAutoCompletePublic?lookupFields=codice&limit=100": "[]",
        "https://planner.example/api/Aule/getPerAutoCompletePublic?lookupFields=codice&limit=100": "[]",
        "https://planner.example/api/Impegni/getImpegniPublic?dataInizio=2020-01-01&dataFine=2030-12-31&limit=20000": "[]",
    }

    aulas = crawl_aulas(
        base_url=base_url,
        client=FakeHttpClient(pages),
        department_urls=(department_url,),
        planner_base_url="https://planner.example",
        planner_client_id=None,
    )

    names = {item.name for item in aulas}
    assert "Aula Apollo" in names
    assert "Aula A Ling." in names

    aula_apollo = next(item for item in aulas if item.name == "Aula Apollo")
    assert aula_apollo.floor == "Piano Terra"
    assert aula_apollo.building_hint == "Cubo 18B"
    assert aula_apollo.capacity == 129


def test_crawl_aulas_parses_department_accordion_entries() -> None:
    base_url = "https://www.unical.it/campus/visita-il-campus/mappa/"
    department_url = "https://ctc.unical.it/dipartimento/organizzazione/strutture/"
    pages = {
        base_url: "<html><body>No map iframe</body></html>",
        department_url: """
            <html><body>
              <div class="accordion accordion-left-icon">
                <div class="accordion-item">
                  <div class="accordion-header">
                    <button class="accordion-button" type="button">Aula CH-15-6A-3T</button>
                  </div>
                  <div class="accordion-collapse collapse">
                    <div class="accordion-body">
                      <ul>
                        <li>Ubicazione: <i>Cubo 15 – Piano 6°</i></li>
                        <li>Capienza: <i>60 posti</i></li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
              <div class="accordion accordion-left-icon">
                <div class="accordion-item">
                  <div class="accordion-header">
                    <button class="accordion-button" type="button">Laboratorio di CHIMICA ANALITICA</button>
                  </div>
                  <div class="accordion-collapse collapse">
                    <div class="accordion-body">
                      <p><i>Ubicazione:</i> <strong>Cubo 15 C</strong> - <strong>piano 1°</strong></p>
                    </div>
                  </div>
                </div>
              </div>
              <div class="accordion accordion-left-icon">
                <div class="accordion-item">
                  <div class="accordion-header">
                    <button class="accordion-button" type="button">Aula Studio</button>
                  </div>
                  <div class="accordion-collapse collapse">
                    <div class="accordion-body">
                      <p>Collocata nell'ex Aula B, secondo piano, Cubo 15 C.</p>
                    </div>
                  </div>
                </div>
              </div>
            </body></html>
        """,
        "https://planner.example/api/Edifici/getPerAutoCompletePublic?lookupFields=codice&limit=100": "[]",
        "https://planner.example/api/Aule/getPerAutoCompletePublic?lookupFields=codice&limit=100": "[]",
        "https://planner.example/api/Impegni/getImpegniPublic?dataInizio=2020-01-01&dataFine=2030-12-31&limit=20000": "[]",
    }

    aulas = crawl_aulas(
        base_url=base_url,
        client=FakeHttpClient(pages),
        department_urls=(department_url,),
        planner_base_url="https://planner.example",
        planner_client_id=None,
    )

    names = {item.name for item in aulas}
    assert "Aula CH-15-6A-3T" in names
    assert "Laboratorio di CHIMICA ANALITICA" in names
    assert "Aula Studio" in names

    aula_ch = next(item for item in aulas if item.name == "Aula CH-15-6A-3T")
    assert aula_ch.floor == "Sesto piano"
    assert aula_ch.building_hint == "Cubo 15A"
    assert aula_ch.capacity == 60

    lab = next(item for item in aulas if item.name == "Laboratorio di CHIMICA ANALITICA")
    assert lab.floor == "Primo piano"
    assert lab.building_hint == "Cubo 15C"

    studio = next(item for item in aulas if item.name == "Aula Studio")
    assert studio.floor == "Secondo piano"
    assert studio.building_hint == "Cubo 15C"
