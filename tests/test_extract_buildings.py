from __future__ import annotations

from unical_scraper.extract.buildings import crawl_buildings


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


def test_crawl_buildings_uses_embedded_google_map_kml() -> None:
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
                    <name>Teatro Piccolo</name>
                    <Point><coordinates>16.2244919,39.3578711,0</coordinates></Point>
                  </Placemark>
                  <Placemark>
                    <name>Fontanella Ingegneria</name>
                    <Point><coordinates>16.2270000,39.3570000,0</coordinates></Point>
                  </Placemark>
                </Folder>
              </Document>
            </kml>
        """,
    }

    buildings = crawl_buildings(base_url=base_url, client=FakeHttpClient(pages))

    assert len(buildings) == 2
    assert buildings[0].name == "Cubo 18B - DiCES"
    assert buildings[0].lat == 39.3605961
    assert buildings[0].lng == 16.2266846
    assert buildings[1].name == "Teatro Piccolo"
