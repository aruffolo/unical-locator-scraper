from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from unical_scraper.cli import cli


def test_crawl_full_command_uses_fast_profile(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    captured_teachers_kwargs: dict[str, object] = {}

    def record(name: str):
        def _recorder(**kwargs: object) -> None:
            calls.append((name, kwargs))
        return _recorder

    def capture_teachers(**kwargs: object) -> None:
        calls.append(("teachers", kwargs))
        captured_teachers_kwargs.update(kwargs)

    monkeypatch.setattr("unical_scraper.cli.crawl_departments_command", record("departments"))
    monkeypatch.setattr("unical_scraper.cli.crawl_buildings_command", record("buildings"))
    monkeypatch.setattr("unical_scraper.cli.crawl_services_command", record("services"))
    monkeypatch.setattr("unical_scraper.cli.crawl_teachers_command", capture_teachers)
    monkeypatch.setattr("unical_scraper.cli.crawl_aulas_command", record("aulas"))
    monkeypatch.setattr("unical_scraper.cli.link_places_buildings_command", record("link_places"))
    monkeypatch.setattr("unical_scraper.cli.link_aliases_command", record("link_aliases"))
    monkeypatch.setattr("unical_scraper.cli.validate_command", record("validate"))
    monkeypatch.setattr("unical_scraper.cli.report_command", record("report"))
    monkeypatch.setattr("unical_scraper.cli.contract_command", record("contract"))

    runner = CliRunner()
    data_dir = tmp_path / "replay"
    result = runner.invoke(
        cli,
        [
            "crawl",
            "full",
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0
    assert [name for name, _ in calls] == [
        "departments",
        "buildings",
        "services",
        "teachers",
        "aulas",
        "link_places",
        "link_aliases",
        "contract",
        "validate",
        "report",
    ]

    aulas_kwargs = dict(calls[4][1])
    assert aulas_kwargs["timeout_seconds"] == 10.0
    assert aulas_kwargs["planner_discovery"] is False
    assert aulas_kwargs["planner_public_links"] is True
    assert aulas_kwargs["planner_impegni"] is False
    assert aulas_kwargs["planner_max_link_ids"] == 1
    assert captured_teachers_kwargs["timeout_seconds"] == 10.0
    assert captured_teachers_kwargs["detail_enrichment"] is False
    assert captured_teachers_kwargs["department_fallback"] is False

    assert (data_dir / "building_entrances.json").exists()
    assert (data_dir / "glossary.json").exists()
    assert (data_dir / "faqs.json").exists()
    assert (data_dir / "people.json").exists()


def test_crawl_full_command_refuses_canonical_dir_without_explicit_flag(monkeypatch) -> None:
    def fail(**kwargs: object) -> None:
        raise AssertionError("crawl steps should not run")

    monkeypatch.setattr("unical_scraper.cli.crawl_departments_command", fail)
    monkeypatch.setattr("unical_scraper.cli.crawl_buildings_command", fail)
    monkeypatch.setattr("unical_scraper.cli.crawl_services_command", fail)
    monkeypatch.setattr("unical_scraper.cli.crawl_teachers_command", fail)
    monkeypatch.setattr("unical_scraper.cli.crawl_aulas_command", fail)
    monkeypatch.setattr("unical_scraper.cli.link_places_buildings_command", fail)
    monkeypatch.setattr("unical_scraper.cli.link_aliases_command", fail)
    monkeypatch.setattr("unical_scraper.cli.validate_command", fail)
    monkeypatch.setattr("unical_scraper.cli.report_command", fail)
    monkeypatch.setattr("unical_scraper.cli.contract_command", fail)

    runner = CliRunner()
    result = runner.invoke(cli, ["crawl", "full"])

    assert result.exit_code != 0
    assert "refuses canonical writes by default" in result.output


def test_crawl_full_command_allows_canonical_dir_with_explicit_flag(monkeypatch) -> None:
    calls: list[str] = []

    def record(name: str):
        def _recorder(**kwargs: object) -> None:
            calls.append(name)
        return _recorder

    monkeypatch.setattr("unical_scraper.cli.crawl_departments_command", record("departments"))
    monkeypatch.setattr("unical_scraper.cli.crawl_buildings_command", record("buildings"))
    monkeypatch.setattr("unical_scraper.cli.crawl_services_command", record("services"))
    monkeypatch.setattr("unical_scraper.cli.crawl_teachers_command", record("teachers"))
    monkeypatch.setattr("unical_scraper.cli.crawl_aulas_command", record("aulas"))
    monkeypatch.setattr("unical_scraper.cli.link_places_buildings_command", record("link_places"))
    monkeypatch.setattr("unical_scraper.cli.link_aliases_command", record("link_aliases"))
    monkeypatch.setattr("unical_scraper.cli.validate_command", record("validate"))
    monkeypatch.setattr("unical_scraper.cli.report_command", record("report"))
    monkeypatch.setattr("unical_scraper.cli.contract_command", record("contract"))

    runner = CliRunner()
    result = runner.invoke(cli, ["crawl", "full", "--allow-canonical-write"])

    assert result.exit_code == 0
    assert calls[0] == "departments"


def test_crawl_full_command_uses_full_profile(monkeypatch, tmp_path: Path) -> None:
    captured_aulas_kwargs: dict[str, object] = {}
    captured_teachers_kwargs: dict[str, object] = {}

    def noop(**kwargs: object) -> None:
        return None

    def capture_teachers(**kwargs: object) -> None:
        captured_teachers_kwargs.update(kwargs)

    def capture_aulas(**kwargs: object) -> None:
        captured_aulas_kwargs.update(kwargs)

    monkeypatch.setattr("unical_scraper.cli.crawl_departments_command", noop)
    monkeypatch.setattr("unical_scraper.cli.crawl_buildings_command", noop)
    monkeypatch.setattr("unical_scraper.cli.crawl_services_command", noop)
    monkeypatch.setattr("unical_scraper.cli.crawl_teachers_command", capture_teachers)
    monkeypatch.setattr("unical_scraper.cli.crawl_aulas_command", capture_aulas)
    monkeypatch.setattr("unical_scraper.cli.link_places_buildings_command", noop)
    monkeypatch.setattr("unical_scraper.cli.link_aliases_command", noop)
    monkeypatch.setattr("unical_scraper.cli.validate_command", noop)
    monkeypatch.setattr("unical_scraper.cli.report_command", noop)
    monkeypatch.setattr("unical_scraper.cli.contract_command", noop)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crawl",
            "full",
            "--profile",
            "full",
            "--data-dir",
            str(tmp_path / "replay"),
        ],
    )

    assert result.exit_code == 0
    assert captured_aulas_kwargs["timeout_seconds"] == 30.0
    assert captured_aulas_kwargs["planner_discovery"] is True
    assert captured_aulas_kwargs["planner_public_links"] is True
    assert captured_aulas_kwargs["planner_impegni"] is True
    assert captured_aulas_kwargs["planner_max_link_ids"] is None
    assert captured_teachers_kwargs["timeout_seconds"] == 30.0
    assert captured_teachers_kwargs["detail_enrichment"] is True
    assert captured_teachers_kwargs["department_fallback"] is True
