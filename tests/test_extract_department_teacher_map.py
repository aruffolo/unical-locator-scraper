from __future__ import annotations

from unical_scraper.extract.department_teacher_map import crawl_department_teacher_map


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


def test_crawl_department_teacher_map_extracts_teacher_slug_and_email_keys() -> None:
    departments = [
        {
            "department_id": "dipartimento-di-matematica-e-informatica",
            "website_url": "https://dmi.unical.it/",
        }
    ]
    pages = {
        "https://dmi.unical.it/": """
            <html><body>
              <a href="/dipartimento/persone/docenti/">Docenti</a>
            </body></html>
        """,
        "https://dmi.unical.it/dipartimento/persone/docenti/": """
            <html><body>
              <a href="https://www.unical.it/storage/teachers/mario.rossi/">Mario Rossi</a>
              <a href="mailto:luca.verdi@unical.it">Mail</a>
            </body></html>
        """,
    }

    mapping = crawl_department_teacher_map(
        departments=departments,
        client=FakeHttpClient(pages),
        max_pages_per_department=4,
    )

    assert mapping["slug:mario.rossi"] == "dipartimento-di-matematica-e-informatica"
    assert mapping["email_local:luca.verdi"] == "dipartimento-di-matematica-e-informatica"


def test_crawl_department_teacher_map_follows_people_pagination_links() -> None:
    departments = [
        {
            "department_id": "dipartimento-di-fisica",
            "website_url": "https://fisica.unical.it/",
        }
    ]
    pages = {
        "https://fisica.unical.it/": "<html><body>Home</body></html>",
        "https://fisica.unical.it/dipartimento/presentazione/persone/": """
            <html><body>
              <a href="/dipartimento/presentazione/persone/?page=2">next ></a>
            </body></html>
        """,
        "https://fisica.unical.it/dipartimento/presentazione/persone/?lang=it": """
            <html><body>
              <a href="/dipartimento/presentazione/persone/?page=2">next ></a>
            </body></html>
        """,
        "https://fisica.unical.it/dipartimento/presentazione/persone/?page=2": """
            <html><body>
              <a href="https://www.unical.it/storage/teachers/anna.rossi/">Anna Rossi</a>
            </body></html>
        """,
    }

    mapping = crawl_department_teacher_map(
        departments=departments,
        client=FakeHttpClient(pages),
        max_pages_per_department=6,
    )

    assert mapping["slug:anna.rossi"] == "dipartimento-di-fisica"


def test_crawl_department_teacher_map_follows_people_category_links() -> None:
    departments = [
        {
            "department_id": "dipartimento-di-chimica-e-tecnologie-chimiche",
            "website_url": "https://ctc.unical.it/",
        }
    ]
    pages = {
        "https://ctc.unical.it/": "<html><body>Home</body></html>",
        "https://ctc.unical.it/dipartimento/presentazione/persone/": """
            <html><body>
              <a href="/dipartimento/presentazione/persone/professori-di-i-fascia/">
                Professori di I fascia
              </a>
            </body></html>
        """,
        "https://ctc.unical.it/dipartimento/presentazione/persone/?lang=it": "<html><body></body></html>",
        "https://ctc.unical.it/dipartimento/presentazione/persone/professori-di-i-fascia/": """
            <html><body>
              <a href="https://www.unical.it/storage/teachers/anna.maria.napoli/">
                Prof.ssa Anna Maria C. NAPOLI
              </a>
            </body></html>
        """,
    }

    mapping = crawl_department_teacher_map(
        departments=departments,
        client=FakeHttpClient(pages),
        max_pages_per_department=6,
    )

    assert (
        mapping["slug:anna.maria.napoli"]
        == "dipartimento-di-chimica-e-tecnologie-chimiche"
    )


def test_crawl_department_teacher_map_uses_addressbook_api_from_people_page() -> None:
    departments = [
        {
            "department_id": "dipartimento-di-biologia-ecologia-e-scienze-della-terra",
            "website_url": "https://dibest.unical.it/",
        }
    ]
    pages = {
        "https://dibest.unical.it/": "<html><body>Home</body></html>",
        "https://dibest.unical.it/dipartimento/presentazione/persone/": """
            <html><body>
              <script>
                let url = "https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree=002014";
              </script>
            </body></html>
        """,
        "https://dibest.unical.it/dipartimento/presentazione/persone/?lang=it": "<html><body></body></html>",
        "https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree=002014": """
            {
              "results": [
                {"ID": "mirellaaurora.aceto", "Name": "ACETO MIRELLA AURORA", "Email": ["mirellaaurora.aceto@unical.it"]}
              ],
              "next": "//storage.portale.unical.it/api/ricerca/addressbook/?page=2&structuretree=002014"
            }
        """,
        "https://storage.portale.unical.it/api/ricerca/addressbook/?page=2&structuretree=002014": """
            {
              "results": [
                {"ID": "rosanna.adduci", "Name": "ADDUCI ROSANNA", "Email": ["rosanna.adduci@unical.it"]}
              ],
              "next": null
            }
        """,
    }

    mapping = crawl_department_teacher_map(
        departments=departments,
        client=FakeHttpClient(pages),
        max_pages_per_department=6,
    )

    expected = "dipartimento-di-biologia-ecologia-e-scienze-della-terra"
    assert mapping["slug:mirellaaurora.aceto"] == expected
    assert mapping["slug:rosanna.adduci"] == expected
    assert mapping["email_local:mirellaaurora.aceto"] == expected
    assert mapping["email_local:rosanna.adduci"] == expected
    assert mapping["name:aceto mirella aurora"] == expected
    assert mapping["name:adduci rosanna"] == expected


def test_crawl_department_teacher_map_extracts_generic_structuretree_pattern() -> None:
    departments = [
        {
            "department_id": "dipartimento-di-fisica",
            "website_url": "https://fisica.unical.it/",
        }
    ]
    pages = {
        "https://fisica.unical.it/": "<html><body>Home</body></html>",
        "https://fisica.unical.it/dipartimento/presentazione/persone/": """
            <html><body>
              <script>
                const cfg = { structuretree: "002019" };
              </script>
            </body></html>
        """,
        "https://fisica.unical.it/dipartimento/presentazione/persone/?lang=it": "<html><body></body></html>",
        "https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree=002019": """
            {
              "results": [{"ID": "anna.rossi", "Email": []}],
              "next": null
            }
        """,
    }

    mapping = crawl_department_teacher_map(
        departments=departments,
        client=FakeHttpClient(pages),
        max_pages_per_department=6,
    )
    assert mapping["slug:anna.rossi"] == "dipartimento-di-fisica"


def test_crawl_department_teacher_map_drops_ambiguous_name_keys() -> None:
    departments = [
        {"department_id": "dep-a", "website_url": "https://a.unical.it/"},
        {"department_id": "dep-b", "website_url": "https://b.unical.it/"},
    ]
    pages = {
        "https://a.unical.it/": "<html></html>",
        "https://a.unical.it/dipartimento/presentazione/persone/": (
            "<script>let url='https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree=000001';</script>"
        ),
        "https://a.unical.it/dipartimento/presentazione/persone/?lang=it": "<html></html>",
        "https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree=000001": (
            '{"results":[{"ID":"x.a","Name":"Mario Rossi","Email":["x.a@unical.it"]}],"next":null}'
        ),
        "https://b.unical.it/": "<html></html>",
        "https://b.unical.it/dipartimento/presentazione/persone/": (
            "<script>let url='https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree=000002';</script>"
        ),
        "https://b.unical.it/dipartimento/presentazione/persone/?lang=it": "<html></html>",
        "https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree=000002": (
            '{"results":[{"ID":"x.b","Name":"Mario Rossi","Email":["x.b@unical.it"]}],"next":null}'
        ),
    }

    mapping = crawl_department_teacher_map(
        departments=departments,
        client=FakeHttpClient(pages),
        max_pages_per_department=4,
    )

    assert "name:mario rossi" not in mapping
    assert mapping["slug:x.a"] == "dep-a"
    assert mapping["slug:x.b"] == "dep-b"
