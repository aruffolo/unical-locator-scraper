from datetime import datetime, timezone

from unical_scraper.extract.departments import RawDepartment
from unical_scraper.extract.teachers import RawTeacher
from unical_scraper.transform.normalize import normalize_departments, normalize_teachers


def test_normalize_teachers_produces_people_schema_shape() -> None:
    raw = [
        RawTeacher(
            full_name="Francesco Scarcello",
            email="francesco.scarcello@unical.it",
            department_name="DIMES",
            source_url="https://www.unical.it/docenti/francesco-scarcello",
            website_url="https://www.unical.it/docenti/francesco-scarcello",
            office_hours="Martedi 10:00 - 12:00",
        )
    ]

    people = normalize_teachers(
        raw_teachers=raw,
        verified_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
    )

    assert len(people) == 1
    person = people[0]
    assert person["person_id"] == "scarcello-francesco"
    assert person["full_name"] == "Francesco Scarcello"
    assert person["role"] == "PROFESSOR"
    assert person["department_id"] == "dimes"
    assert person["source_id"] == "unical-teachers"
    assert person["last_verified_at"] == "2026-02-09T00:00:00+00:00"


def test_normalize_departments_produces_departments_schema_shape() -> None:
    raw = [
        RawDepartment(
            name="Dipartimento di Ingegneria Informatica, Modellistica, Elettronica e Sistemistica",
            source_url="https://www.unical.it/ateneo/dipartimenti/dimes",
            email="segreteria@dimes.unical.it",
            phone="+39 0984 123456",
            website_url="https://dimes.unical.it",
        )
    ]

    departments = normalize_departments(
        raw_departments=raw,
        verified_at=datetime(2026, 2, 9, tzinfo=timezone.utc),
    )

    assert len(departments) == 1
    department = departments[0]
    assert department["department_id"] == "dipartimento-di-ingegneria-informatica-modellistica-elettronica-e-sistemistica"
    assert department["name"] == raw[0].name
    assert department["email"] == "segreteria@dimes.unical.it"
    assert department["source_id"] == "unical-departments"
    assert department["last_verified_at"] == "2026-02-09T00:00:00+00:00"
