from __future__ import annotations

import json
from pathlib import Path

from unical_scraper.validate.report import build_coverage_report


def test_build_coverage_report_includes_aulas_and_places_metrics(tmp_path: Path) -> None:
    (tmp_path / "buildings.json").write_text(
        json.dumps(
            [
                {"building_id": "cubo-18b", "name": "Cubo 18B", "lat": 39.36, "lng": 16.22},
                {"building_id": "cubo-34b", "name": "Cubo 34B"},
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "departments.json").write_text(
        json.dumps([{"department_id": "dimes", "name": "DIMES", "email": "x@unical.it"}]),
        encoding="utf-8",
    )
    (tmp_path / "places.json").write_text(
        json.dumps(
            [
                {"place_id": "aula-p2", "type": "AULA", "name": "Aula P2", "building_id": "cubo-18b"},
                {"place_id": "service-1", "type": "SERVICE", "name": "Servizio"},
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "aulas.json").write_text(
        json.dumps(
            [
                {
                    "aula_id": "aula-p2",
                    "place_id": "aula-p2",
                    "name": "Aula P2",
                    "building_id": "cubo-18b",
                    "floor": "1",
                    "short_code": "P2",
                    "capacity": 120,
                },
                {"aula_id": "aula-p3", "place_id": "aula-p3", "name": "Aula P3"},
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "people.json").write_text(
        json.dumps(
            [
                {"person_id": "a", "full_name": "A", "role": "PROFESSOR", "email": "a@unical.it"},
                {"person_id": "b", "full_name": "B", "role": "PROFESSOR"},
            ]
        ),
        encoding="utf-8",
    )

    report = build_coverage_report(
        data_dir=tmp_path,
        schema_results={"people.json": [], "places.json": [], "aulas.json": []},
        integrity_issues=[],
    )

    assert report["coverage"]["buildings"]["total"] == 2
    assert report["coverage"]["buildings"]["with_coordinates"] == 1
    assert report["coverage"]["places"]["type_aula"] == 1
    assert report["coverage"]["aulas"]["total"] == 2
    assert report["coverage"]["aulas"]["with_building_id"] == 1
    assert report["coverage"]["aulas"]["missing_building_id"] == 1
    assert report["coverage"]["aulas"]["with_floor"] == 1
    assert report["coverage"]["aulas"]["with_short_code"] == 1
    assert report["coverage"]["aulas"]["with_capacity"] == 1
    assert report["coverage"]["aulas"]["missing_building_by_source"][0]["count"] == 1
    assert report["coverage"]["aulas"]["missing_building_examples"][0]["aula_id"] == "aula-p3"


def test_build_coverage_report_includes_scrape_diagnostics_warnings(tmp_path: Path) -> None:
    (tmp_path / "buildings.json").write_text("[]", encoding="utf-8")
    (tmp_path / "departments.json").write_text("[]", encoding="utf-8")
    (tmp_path / "places.json").write_text("[]", encoding="utf-8")
    (tmp_path / "aulas.json").write_text("[]", encoding="utf-8")
    (tmp_path / "people.json").write_text("[]", encoding="utf-8")
    (tmp_path / "scrape_diagnostics.json").write_text(
        json.dumps(
            {
                "sources": {
                    "unical-aulas": {
                        "final_failures": 1,
                        "failure_budget": 2,
                    },
                    "unical-teachers": {
                        "final_failures": 3,
                        "failure_budget": 1,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    report = build_coverage_report(
        data_dir=tmp_path,
        schema_results={},
        integrity_issues=[],
    )

    scrape_diagnostics = report["scrape_diagnostics"]
    assert list(scrape_diagnostics["sources"].keys()) == ["unical-aulas", "unical-teachers"]
    assert scrape_diagnostics["warning_count"] == 2
    assert scrape_diagnostics["warnings"][0]["message"] == "unical-aulas: 1 final failures (budget 2)"
    assert (
        scrape_diagnostics["warnings"][1]["message"]
        == "unical-teachers: 3 final failures (budget 1) [EXCEEDED]"
    )
