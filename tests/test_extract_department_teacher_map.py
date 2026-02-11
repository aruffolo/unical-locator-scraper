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
