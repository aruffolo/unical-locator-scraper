from __future__ import annotations

from unical_scraper.extract.aulas import crawl_aulas


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


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
                <tr><th>Aula</th><th>Cubo</th></tr>
                <tr><td>P2</td><td>Cubo 30C Piano II</td></tr>
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
    }

    aulas = crawl_aulas(
        base_url=base_url,
        client=FakeHttpClient(pages),
        department_urls=(department_url,),
        planner_base_url=planner_base_url,
    )

    names = {item.name for item in aulas}
    assert "Aula P2" in names
    assert "Aula CLA" in names
    assert "Aula P5" in names
    assert "Studio Docente" not in names

    aula_p2 = next(item for item in aulas if item.name == "Aula P2")
    assert aula_p2.floor == "Secondo piano"
    assert aula_p2.building_hint == "Cubo 30C"
