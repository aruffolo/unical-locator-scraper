from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from unical_scraper.cli import cli


def test_crawl_aulas_command_wires_control_flags(monkeypatch, tmp_path: Path) -> None:
    buildings_file = tmp_path / "buildings.json"
    places_file = tmp_path / "places.json"
    aulas_file = tmp_path / "aulas.json"
    buildings_file.write_text("[]", encoding="utf-8")
    places_file.write_text("[]", encoding="utf-8")

    captured_http_kwargs: dict[str, object] = {}
    captured_crawl_kwargs: dict[str, object] = {}

    class FakeHttpClient:
        def __init__(self, **kwargs: object) -> None:
            captured_http_kwargs.update(kwargs)

        def __enter__(self) -> "FakeHttpClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    def fake_crawl_aulas(**kwargs: object) -> list[object]:
        captured_crawl_kwargs.update(kwargs)
        return []

    monkeypatch.setattr("unical_scraper.cli.HttpClient", FakeHttpClient)
    monkeypatch.setattr("unical_scraper.cli.crawl_aulas", fake_crawl_aulas)
    monkeypatch.setattr("unical_scraper.cli.normalize_aulas", lambda raw_aulas, buildings: ([], []))
    monkeypatch.setattr("unical_scraper.cli._emit_http_diagnostics", lambda client: {"final_failures": 0})
    monkeypatch.setattr("unical_scraper.cli._apply_manual_corrections_for_paths", lambda paths: None)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crawl",
            "aulas",
            "--aulas-file",
            str(aulas_file),
            "--places-file",
            str(places_file),
            "--buildings-file",
            str(buildings_file),
            "--timeout",
            "12.5",
            "--no-planner-discovery",
            "--no-planner-public-links",
            "--no-planner-impegni",
            "--planner-max-link-ids",
            "7",
        ],
    )

    assert result.exit_code == 0
    assert captured_http_kwargs["timeout_seconds"] == 12.5
    assert captured_crawl_kwargs["planner_enable_discovery"] is False
    assert captured_crawl_kwargs["planner_enable_public_links"] is False
    assert captured_crawl_kwargs["planner_enable_impegni"] is False
    assert captured_crawl_kwargs["planner_max_link_ids"] == 7
