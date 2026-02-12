from __future__ import annotations

from pathlib import Path

from unical_scraper.extract.teachers import crawl_teachers


class FakeHttpClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get_text(self, url: str) -> str:
        return self._pages[url]


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "teachers"


def _fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


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
                  "TeacherID": "teacher-mario",
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
                  "TeacherID": "teacher-anna",
                  "TeacherName": "Anna Bianchi",
                  "TeacherDepartmentName": "DIBEST",
                  "Email": []
                }
              ],
              "next": null
            }
        """,
        "https://storage.portale.unical.it/api/ricerca/teachers/teacher-mario/?format=json": """
            {
              "results": {
                "TeacherDepartmentName": "DIMES",
                "TeacherOfficeReference": ["Cubo 3C Piano 2 Stanza 8"],
                "ReceptionHours": "Mercoledi 11:00-13:00"
              }
            }
        """,
        "https://storage.portale.unical.it/api/ricerca/teachers/teacher-anna/?format=json": """
            {
              "results": {
                "TeacherDepartmentName": "DIBEST"
              }
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
    assert teachers[1].office_reference == "Cubo 3C Piano 2 Stanza 8"
    assert teachers[1].office_hours == "Mercoledi 11:00-13:00"


def test_crawl_teachers_discovers_api_url_from_script() -> None:
    base_url = "https://www.unical.it/storage/teachers/"
    api_url_with_page_size = (
        "https://storage.portale.unical.it/api/ricerca/teachers/?format=json&page_size=200"
    )
    pages = {
        base_url: _fixture("index_with_script_api.html"),
        api_url_with_page_size: """
            {
              "results": [
                {
                  "TeacherID": "teacher-123",
                  "TeacherName": "Rosa Adamo",
                  "TeacherDepartmentName": "DISAG",
                  "Email": ["rosa.adamo@unical.it"]
                }
              ],
              "next": null
            }
        """,
        "https://storage.portale.unical.it/api/ricerca/teachers/teacher-123/?format=json": """
            {
              "results": {
                "TeacherDepartmentName": "DISAG",
                "TeacherOfficeReference": ["Cubo 3C"]
              }
            }
        """,
    }

    teachers = crawl_teachers(base_url=base_url, client=FakeHttpClient(pages))

    assert len(teachers) == 1
    assert teachers[0].full_name == "Rosa Adamo"
    assert teachers[0].email == "rosa.adamo@unical.it"
    assert teachers[0].website_url == "https://www.unical.it/storage/teachers/rosa.adamo/"


def test_crawl_teachers_keeps_list_department_when_detail_department_missing() -> None:
    base_url = "https://www.unical.it/storage/teachers/"
    api_url_with_page_size = (
        "https://storage.portale.unical.it/api/ricerca/teachers/?format=json&page_size=200"
    )
    pages = {
        base_url: """
            <html><body>
              <script>
                const endpoint = "https://storage.portale.unical.it/api/ricerca/teachers/?format=json";
              </script>
            </body></html>
        """,
        api_url_with_page_size: """
            {
              "results": [
                {
                  "TeacherID": "teacher-x",
                  "TeacherName": "X Name",
                  "TeacherDepartmentName": "Dipartimento di Fisica",
                  "TeacherDepartmentCod": "002019",
                  "Email": []
                }
              ],
              "next": null
            }
        """,
        "https://storage.portale.unical.it/api/ricerca/teachers/teacher-x/?format=json": """
            {
              "results": {
                "TeacherDepartmentName": null
              }
            }
        """,
    }

    teachers = crawl_teachers(base_url=base_url, client=FakeHttpClient(pages))

    assert len(teachers) == 1
    assert teachers[0].department_name == "Dipartimento di Fisica"
    assert teachers[0].department_code == "002019"


def test_crawl_teachers_parses_embedded_profile_payload() -> None:
    base_url = "https://www.unical.it/storage/teachers/"
    detail_url = "https://www.unical.it/storage/teachers/rosa.adamo/"
    pages = {
        base_url: """
            <html><body>
              <a href="/storage/teachers/rosa.adamo/?lang=it">Rosa Adamo</a>
            </body></html>
        """,
        detail_url: _fixture("detail_with_payload.html"),
    }

    teachers = crawl_teachers(base_url=base_url, client=FakeHttpClient(pages))

    assert len(teachers) == 1
    teacher = teachers[0]
    assert teacher.full_name == "Rosa ADAMO"
    assert teacher.email == "rosa.adamo@unical.it"
    assert teacher.phone == "0984/492272"
    assert teacher.department_name == "Dipartimento di Scienze Aziendali e Giuridiche"
    assert teacher.office_hours == "Lunedi 10:00-12:00"
    assert teacher.website_url == "https://example.org/profile"
    assert teacher.notes == (
        "Office: Dipartimento di Scienze Aziendali e Giuridiche | Office references: Cubo 3C"
    )
