from __future__ import annotations

from unical_scraper.extract.services import _canonical_service_url, crawl_services


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        if url in self._pages:
            return self._pages[url]
        if url.endswith("/") and url[:-1] in self._pages:
            return self._pages[url[:-1]]
        if f"{url}/" in self._pages:
            return self._pages[f"{url}/"]
        raise KeyError(url)


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


def test_crawl_services_excludes_nested_event_and_news_pages() -> None:
    base_url = "https://www.unical.it/campus/servizi/"
    pages = {
        base_url: """
            <html><body><main>
              <a href="/campus/vivere-il-campus/socialita/">Socialita</a>
              <a href="/campus/vivere-il-campus/centro-sanitario/">Centro Sanitario</a>
            </main></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/socialita/": """
            <html><body><main>
              <a href="/campus/vivere-il-campus/socialita/unicalfesta/">UNICALFESTA</a>
              <a href="/campus/vivere-il-campus/socialita/centri-comuni/">Centri comuni</a>
            </main><h1>Socialita</h1><p>Socialita nel campus.</p></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/centro-sanitario/": """
            <html><body><main>
              <a href="/campus/vivere-il-campus/centro-sanitario/contents/news/view/1-foo/">News</a>
            </main><h1>Centro Sanitario</h1><p>Servizio sanitario del campus.</p></body></html>
        """,
    }

    services = crawl_services(base_url=base_url, client=FakeHttpClient(pages))
    names = {service.name for service in services}

    assert "Socialita" in names
    assert "Centro Sanitario" in names
    assert "UNICALFESTA" not in names
    assert "Centri comuni" not in names


def test_crawl_services_skips_unfetchable_detail_pages() -> None:
    base_url = "https://www.unical.it/campus/servizi/"
    pages = {
        base_url: """
            <html><body><main>
              <a href="/campus/vivere-il-campus/centro-sanitario/">Centro Sanitario</a>
              <a href="/campus/vivere-il-campus/non-esiste/">Non Esiste</a>
            </main></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/centro-sanitario/": """
            <html><body><h1>Centro Sanitario</h1><p>Servizio sanitario del campus.</p></body></html>
        """,
    }

    services = crawl_services(base_url=base_url, client=FakeHttpClient(pages))

    assert len(services) == 1
    assert services[0].name == "Centro Sanitario"


def test_crawl_services_ignores_media_archive_links() -> None:
    base_url = "https://www.unical.it/campus/servizi/"
    pages = {
        base_url: """
            <html><body><main>
              <a href="/campus/vivere-il-campus/centro-sanitario/">Centro Sanitario</a>
              <a href="/media/medias/2025/">Media 2025</a>
              <a href="/media/medias/2021/">Media 2021</a>
            </main></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/centro-sanitario/": """
            <html><body><h1>Centro Sanitario</h1><p>Servizio sanitario del campus.</p></body></html>
        """,
    }

    services = crawl_services(base_url=base_url, client=FakeHttpClient(pages))

    assert len(services) == 1
    assert services[0].name == "Centro Sanitario"


def test_crawl_services_uses_slug_when_heading_is_generic() -> None:
    base_url = "https://www.unical.it/campus/servizi/"
    pages = {
        base_url: """
            <html><body><main>
              <a href="/campus/vivere-il-campus/biblioteche/">Biblioteche</a>
            </main></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/biblioteche/": """
            <html><body>
              <h1>Vivere il campus</h1>
              <p>Vai a tutte le notizie</p>
            </body></html>
        """,
    }

    services = crawl_services(base_url=base_url, client=FakeHttpClient(pages))

    assert len(services) == 1
    assert services[0].name == "Biblioteche"
    assert services[0].description is None


def test_crawl_services_splits_sistema_museale_subpages() -> None:
    base_url = "https://www.unical.it/campus/servizi/"
    pages = {
        base_url: """
            <html><body><main>
              <a href="/campus/vivere-il-campus/sistema-museale/">Sistema Museale</a>
            </main></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/sistema-museale/": """
            <html><body><main>
              <a href="/campus/vivere-il-campus/sistema-museale/accesso-ai-musei/">Accesso ai musei</a>
              <a href="/campus/vivere-il-campus/sistema-museale/musnob/">MuSNOB</a>
              <a href="/campus/vivere-il-campus/sistema-museale/rimuseum/">RiMuseum</a>
              <a href="/campus/vivere-il-campus/sistema-museale/miai/">MIAI</a>
            </main><h1>Sistema Museale</h1></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/sistema-museale/musnob/": """
            <html><body><main>
              <a href="/campus/vivere-il-campus/sistema-museale/musnob/paleontologia/">Paleontologia</a>
            </main><h1>MuSNOB</h1></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/sistema-museale/musnob/paleontologia/": """
            <html><body><h1>MuSNOB</h1><p>Via Pietro Bucci, cubo 14/b.</p></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/sistema-museale/rimuseum/": """
            <html><body><h1>Sistema Museale</h1><p>Via Cavour, 1 - Rende.</p></body></html>
        """,
        "https://www.unical.it/campus/vivere-il-campus/sistema-museale/miai/": """
            <html><body><h1>Sistema Museale</h1><p>Museo interattivo.</p></body></html>
        """,
    }

    services = crawl_services(base_url=base_url, client=FakeHttpClient(pages))
    names = {service.name for service in services}

    assert "Sistema Museale" not in names
    assert "Accesso Ai Musei" not in names
    assert "MuSNOB" in names
    assert "Paleontologia" in names
    assert "Rimuseum" in names
    assert "Miai" in names


def test_canonical_service_url_maps_nested_pages_to_parent_service_page() -> None:
    assert (
        _canonical_service_url(
            "https://www.unical.it/campus/vivere-il-campus/centro-sanitario/laboratorio-di-chimica-clinica-e-tossicologia/"
        )
        == "https://www.unical.it/campus/vivere-il-campus/centro-sanitario/"
    )
    assert (
        _canonical_service_url(
            "https://www.unical.it/didattica/diritto-allo-studio/borse-di-studio/bandi-diritto-allo-studio/"
        )
        == "https://www.unical.it/didattica/diritto-allo-studio/borse-di-studio/"
    )
    assert (
        _canonical_service_url(
            "https://www.unical.it/campus/vivere-il-campus/socialita/unicalfesta/"
        )
        is None
    )
    assert (
        _canonical_service_url("https://www.unical.it/didattica/diritto-allo-studio/step/")
        is None
    )
    assert _canonical_service_url("https://www.unical.it/media/medias/2025/") is None
    assert (
        _canonical_service_url(
            "https://www.unical.it/campus/vivere-il-campus/sistema-museale/musnob/paleontologia/"
        )
        == "https://www.unical.it/campus/vivere-il-campus/sistema-museale/musnob/paleontologia/"
    )
    assert (
        _canonical_service_url(
            "https://www.unical.it/campus/vivere-il-campus/sistema-museale/rimuseum/"
        )
        == "https://www.unical.it/campus/vivere-il-campus/sistema-museale/rimuseum/"
    )
    assert (
        _canonical_service_url(
            "https://www.unical.it/campus/vivere-il-campus/sistema-museale/accesso-ai-musei/"
        )
        is None
    )
