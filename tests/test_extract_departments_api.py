from __future__ import annotations

from unical_scraper.extract.departments import crawl_departments


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


def test_crawl_departments_uses_embedded_api_endpoint() -> None:
    base_url = "https://www.unical.it/organizzazione/strutture/dipartimenti/"
    api_url = "https://storage.portale.unical.it/api/ricerca/structures/?father=170005&type=DIP&page_size=50&lang=it"

    pages = {
        base_url: f"""
            <html><body>
              <script>
                let url = \"{api_url}\";
              </script>
            </body></html>
        """,
        api_url: """
            {
              "results": [
                {
                  "StructureName": "Dipartimento di Ingegneria Informatica, Modellistica, Elettronica e Sistemistica",
                  "StructureURL": "https://dimes.unical.it"
                },
                {
                  "StructureName": "Dipartimento di Biologia, Ecologia e Scienze della Terra",
                  "StructureURL": "https://dibest.unical.it"
                }
              ],
              "next": null
            }
        """,
    }

    departments = crawl_departments(base_url=base_url, client=FakeHttpClient(pages))

    assert len(departments) == 2
    assert departments[0].name == "Dipartimento di Biologia, Ecologia e Scienze della Terra"
    assert departments[0].website_url == "https://dibest.unical.it"
    assert departments[1].name.startswith("Dipartimento di Ingegneria Informatica")
    assert departments[1].website_url == "https://dimes.unical.it"
