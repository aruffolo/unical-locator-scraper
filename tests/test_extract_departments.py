from __future__ import annotations

from unical_scraper.extract.departments import crawl_departments


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


def test_crawl_departments_discovers_and_parses_detail_pages() -> None:
    base_url = "https://www.unical.it/ateneo/dipartimenti"
    pages = {
        base_url: """
            <html><body>
              <a href="/ateneo/dipartimenti/dimes">DIMES</a>
              <a href="/ateneo/dipartimenti/dispes">DISPES</a>
              <a href="/ateneo/dipartimenti/dimes">DIMES Duplicate</a>
              <a href="https://example.org/other">External</a>
            </body></html>
        """,
        "https://www.unical.it/ateneo/dipartimenti/dimes": """
            <html><body>
              <h1>Dipartimento di Ingegneria Informatica</h1>
              <a href="mailto:segreteria@dimes.unical.it">Mail</a>
              <a href="tel:+390984123456">Telefono</a>
              <a href="https://dimes.unical.it">Sito web</a>
            </body></html>
        """,
        "https://www.unical.it/ateneo/dipartimenti/dispes": """
            <html><body>
              <h1>Dipartimento di Scienze Politiche e Sociali</h1>
              <a href="mailto:info@dispes.unical.it">Mail</a>
              <a href="https://dispes.unical.it">Website</a>
            </body></html>
        """,
    }

    departments = crawl_departments(base_url=base_url, client=FakeHttpClient(pages))

    assert len(departments) == 2
    assert departments[0].name == "Dipartimento di Ingegneria Informatica"
    assert departments[0].email == "segreteria@dimes.unical.it"
    assert departments[0].phone == "+390984123456"
    assert departments[0].website_url == "https://dimes.unical.it"

    assert departments[1].name == "Dipartimento di Scienze Politiche e Sociali"
    assert departments[1].email == "info@dispes.unical.it"


def test_crawl_departments_fallback_single_page() -> None:
    base_url = "https://www.unical.it/ateneo/dipartimenti/dimes"
    pages = {
        base_url: """
            <html><head><title>Dipartimento DIMES</title></head><body>
              <h1>Dipartimento DIMES</h1>
              <a href="mailto:segreteria@dimes.unical.it">Mail</a>
            </body></html>
        """
    }

    departments = crawl_departments(base_url=base_url, client=FakeHttpClient(pages))

    assert len(departments) == 1
    assert departments[0].name == "Dipartimento DIMES"
    assert departments[0].email == "segreteria@dimes.unical.it"
    assert departments[0].source_url == base_url
