from __future__ import annotations

from unical_scraper.extract.teachers import crawl_teachers


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


def test_crawl_teachers_uses_embedded_api_endpoint() -> None:
    base_url = "https://www.unical.it/storage/teachers/"
    api_url = "https://storage.portale.unical.it/api/ricerca/teachers/?format=json"
    api_url_with_page_size = (
        "https://storage.portale.unical.it/api/ricerca/teachers/?format=json&page_size=200"
    )
    api_page_2 = (
        "https://storage.portale.unical.it/api/ricerca/teachers/?format=json&page=2&page_size=200"
    )

    pages = {
        base_url: f"""
            <html><body>
              <main>
                <a href=\"{api_url}\">Json</a>
              </main>
            </body></html>
        """,
        api_url_with_page_size: """
            {
              "results": [
                {
                  "TeacherName": "Mario Rossi",
                  "TeacherDepartmentName": "DIMES",
                  "Email": ["mario.rossi@unical.it"]
                }
              ],
              "next": "//storage.portale.unical.it/api/ricerca/teachers/?format=json&page=2"
            }
        """,
        api_page_2: """
            {
              "results": [
                {
                  "TeacherName": "Anna Bianchi",
                  "TeacherDepartmentName": "DIBEST",
                  "Email": []
                }
              ],
              "next": null
            }
        """,
    }

    teachers = crawl_teachers(base_url=base_url, client=FakeHttpClient(pages))

    assert len(teachers) == 2
    assert teachers[0].full_name == "Anna Bianchi"
    assert teachers[0].department_name == "DIBEST"
    assert teachers[0].email is None

    assert teachers[1].full_name == "Mario Rossi"
    assert teachers[1].email == "mario.rossi@unical.it"
    assert teachers[1].website_url == "https://www.unical.it/storage/teachers/mario.rossi/"
