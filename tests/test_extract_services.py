from __future__ import annotations

from unical_scraper.extract.services import crawl_services


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


def test_crawl_services_discovers_and_parses_detail_pages() -> None:
    base_url = "https://www.unical.it/ateneo/servizi"
    pages = {
        base_url: """
            <html><body>
              <a href="/ateneo/servizi/segreteria-studenti">Segreteria Studenti</a>
              <a href="/ateneo/servizi/ufficio-orientamento">Ufficio Orientamento</a>
              <a href="https://example.org/external">External</a>
            </body></html>
        """,
        "https://www.unical.it/ateneo/servizi/segreteria-studenti": """
            <html><body>
              <h1>Segreteria Studenti</h1>
              <p>Supporto iscrizioni e certificati.</p>
              <a href="mailto:segreteria@unical.it">Mail</a>
              <a href="tel:+390984123123">Telefono</a>
            </body></html>
        """,
        "https://www.unical.it/ateneo/servizi/ufficio-orientamento": """
            <html><body>
              <h1>Ufficio Orientamento</h1>
              <p>Supporto matricole.</p>
              <a href="https://www.unical.it/orientamento">Sito</a>
            </body></html>
        """,
    }

    services = crawl_services(base_url=base_url, client=FakeHttpClient(pages))

    assert len(services) == 2
    assert services[0].name == "Ufficio Orientamento"
    assert services[0].service_type == "OFFICE"
    assert services[1].name == "Segreteria Studenti"
    assert services[1].service_type == "SECRETARY"
    assert services[1].email == "segreteria@unical.it"


def test_crawl_services_fallback_parses_cards_on_index_page() -> None:
    base_url = "https://www.unical.it/servizi-campus"
    pages = {
        base_url: """
            <html><body>
              <article class="card">
                <h3>Servizio Bibliotecario</h3>
                <p>Prestito e consultazione.</p>
                <a href="mailto:biblioteca@unical.it">Mail</a>
              </article>
              <article class="card">
                <h3>Segreteria Didattica</h3>
                <p>Informazioni studenti.</p>
              </article>
            </body></html>
        """
    }

    services = crawl_services(base_url=base_url, client=FakeHttpClient(pages))

    assert len(services) == 2
    assert services[0].name == "Segreteria Didattica"
    assert services[0].service_type == "SECRETARY"
    assert services[1].name == "Servizio Bibliotecario"
    assert services[1].service_type == "SERVICE"
