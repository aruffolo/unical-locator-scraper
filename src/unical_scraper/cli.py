"""CLI entrypoint for the UNICAL scraping pipeline."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from .extract.aulas import crawl_aulas
from .extract.buildings import crawl_buildings
from .extract.department_teacher_map import crawl_department_teacher_map
from .extract.departments import crawl_departments
from .extract.services import crawl_services
from .extract.teachers import crawl_teachers
from .transform.aliases import build_search_aliases
from .transform.normalize import (
    normalize_teacher_office_places,
    normalize_aulas,
    normalize_buildings,
    normalize_departments,
    normalize_services,
    normalize_teachers,
    write_json,
)
from .transform.linking import link_places_to_buildings
from .transform.manual_corrections import (
    ManualCorrectionsError,
    apply_manual_corrections_to_data_dir,
)
from .utils.html_cache import HtmlCache
from .utils.http import DEFAULT_USER_AGENT, HttpClient
from .validate.integrity import check_integrity, issues_to_dicts
from .validate.jsonschema_validate import validate_dataset_dir
from .validate.report import build_coverage_report
from .validate.contract import build_dataset_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "normalized"
DEFAULT_SCHEMAS_DIR = REPO_ROOT / "data" / "schema"
DEFAULT_CORRECTIONS_FILE = REPO_ROOT / "data" / "corrections" / "manual_corrections.yaml"
DEFAULT_DESTRUCTIVE_ALLOWLIST_FILE = (
    REPO_ROOT / "data" / "corrections" / "destructive_allowlist.yaml"
)
DEFAULT_TEACHERS_BASE_URL = "https://www.unical.it/storage/teachers/"
DEFAULT_DEPARTMENTS_BASE_URL = "https://www.unical.it/organizzazione/strutture/dipartimenti/"
DEFAULT_SERVICES_BASE_URL = "https://www.unical.it/campus/servizi/"
DEFAULT_BUILDINGS_BASE_URL = "https://www.unical.it/campus/visita-il-campus/mappa/"
DEFAULT_AULAS_BASE_URL = "https://www.unical.it/campus/visita-il-campus/mappa/"
DEFAULT_CONTRACT_COMPATIBILITY_VERSION = 1
DEFAULT_CONTRACT_VERSION = "1.0.0"
STATIC_DATASET_PLACEHOLDERS = {
    "building_entrances.json": [],
    "glossary.json": [],
    "faqs.json": [],
    "people.json": [],
}
BASELINE_PRESERVED_DATASETS: dict[str, str] = {
    "aulas": "place_id",
    "buildings": "building_id",
    "departments": "department_id",
    "people": "person_id",
    "places": "place_id",
}


def _is_canonical_data_dir(path: Path) -> bool:
    return path.resolve() == DEFAULT_DATA_DIR.resolve()


@dataclass(frozen=True)
class FullCrawlProfile:
    aulas_failure_budget: int
    aulas_planner_discovery: bool
    aulas_planner_impegni: bool
    aulas_planner_max_link_ids: int | None
    aulas_planner_public_links: bool
    aulas_timeout_seconds: float
    services_failure_budget: int
    teachers_enabled: bool
    teachers_detail_enrichment: bool
    teachers_department_fallback: bool
    teachers_failure_budget: int
    teachers_timeout_seconds: float


FULL_CRAWL_PROFILES = {
    "fast": FullCrawlProfile(
        services_failure_budget=0,
        teachers_enabled=True,
        teachers_detail_enrichment=False,
        teachers_failure_budget=10,
        teachers_department_fallback=False,
        teachers_timeout_seconds=10.0,
        aulas_failure_budget=10,
        aulas_timeout_seconds=10.0,
        aulas_planner_discovery=False,
        aulas_planner_public_links=True,
        aulas_planner_impegni=False,
        aulas_planner_max_link_ids=1,
    ),
    "full": FullCrawlProfile(
        services_failure_budget=0,
        teachers_enabled=True,
        teachers_detail_enrichment=True,
        teachers_failure_budget=10,
        teachers_department_fallback=True,
        teachers_timeout_seconds=30.0,
        aulas_failure_budget=10,
        aulas_timeout_seconds=30.0,
        aulas_planner_discovery=True,
        aulas_planner_public_links=True,
        aulas_planner_impegni=True,
        aulas_planner_max_link_ids=None,
    ),
}


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _upsert_source_entry(sources_file: Path, source_entry: dict[str, str]) -> None:
    existing = _load_json_array(sources_file)
    by_id: dict[str, dict[str, Any]] = {
        str(item["source_id"]): item for item in existing if item.get("source_id")
    }
    by_id[source_entry["source_id"]] = source_entry
    sorted_entries = sorted(by_id.values(), key=lambda item: str(item["source_id"]))
    write_json(sources_file, sorted_entries)


def _merge_places_with_aulas(
    existing_places: list[dict[str, Any]],
    aula_places: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    preserved_places = [
        place
        for place in existing_places
        if not (place.get("type") == "AULA" and place.get("source_id") == "unical-aulas")
    ]
    by_id: dict[str, dict[str, Any]] = {
        str(item["place_id"]): item for item in preserved_places if item.get("place_id")
    }
    for place in aula_places:
        place_id = place.get("place_id")
        if not place_id:
            continue
        by_id[str(place_id)] = place
    return sorted(by_id.values(), key=lambda item: str(item.get("place_id", "")))


def _emit_http_diagnostics(client: HttpClient) -> dict[str, Any]:
    summary = client.diagnostics_summary()
    click.echo(f"HTTP diagnostics: {json.dumps(summary, sort_keys=True)}")
    return summary


def _record_scrape_diagnostics(
    *,
    data_dir: Path,
    source_id: str,
    summary: dict[str, Any],
    failure_budget: int,
) -> None:
    diagnostics_file = data_dir / "scrape_diagnostics.json"
    payload = _load_json_object(diagnostics_file)
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        sources = {}

    final_failures = int(summary.get("final_failures", 0) or 0)
    diagnostics_entry = {
        "source_id": source_id,
        "requests": int(summary.get("requests", 0) or 0),
        "attempts": int(summary.get("attempts", 0) or 0),
        "retries": int(summary.get("retries", 0) or 0),
        "final_failures": final_failures,
        "failure_budget": max(failure_budget, 0),
        "status": "warning" if final_failures > max(failure_budget, 0) else "ok",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    sources[source_id] = diagnostics_entry
    payload["sources"] = {key: sources[key] for key in sorted(sources)}
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(diagnostics_file, payload)


def _enforce_failure_budget(source_id: str, summary: dict[str, Any], failure_budget: int) -> None:
    final_failures = int(summary.get("final_failures", 0) or 0)
    budget = max(failure_budget, 0)
    if final_failures == 0:
        return
    click.echo(
        f"[WARN] {source_id}: {final_failures} final HTTP failures detected "
        f"(budget: {budget})."
    )
    if final_failures > budget:
        raise SystemExit(
            f"{source_id} exceeded HTTP failure budget: {final_failures} > {budget}"
        )


def _apply_manual_corrections_for_paths(paths: list[Path]) -> None:
    grouped_dataset_names: dict[Path, set[str]] = {}
    for path in paths:
        if path.suffix != ".json":
            continue
        grouped_dataset_names.setdefault(path.parent, set()).add(path.name)

    for data_dir, dataset_names in grouped_dataset_names.items():
        if not DEFAULT_CORRECTIONS_FILE.exists() or not DEFAULT_DESTRUCTIVE_ALLOWLIST_FILE.exists():
            click.echo(
                "[WARN] correction files missing; skipped manual correction apply "
                f"for {data_dir}"
            )
            continue

        try:
            summary = apply_manual_corrections_to_data_dir(
                data_dir=data_dir,
                registry_path=DEFAULT_CORRECTIONS_FILE,
                allowlist_path=DEFAULT_DESTRUCTIVE_ALLOWLIST_FILE,
                dataset_names=dataset_names,
            )
        except ManualCorrectionsError as exc:
            raise SystemExit(f"manual corrections failed: {exc}") from exc
        if summary.fields_changed > 0:
            click.echo(
                "Applied manual corrections: "
                f"datasets={len(summary.datasets_scanned)} "
                f"rules={summary.rules_applied} "
                f"field_changes={summary.fields_changed}"
            )


def _ensure_static_dataset_placeholders(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for dataset_name, payload in STATIC_DATASET_PLACEHOLDERS.items():
        dataset_path = data_dir / dataset_name
        if dataset_path.exists():
            continue
        write_json(dataset_path, payload)


def _dataset_paths(data_dir: Path) -> dict[str, Path]:
    return {
        "aliases": data_dir / "aliases.json",
        "aulas": data_dir / "aulas.json",
        "buildings": data_dir / "buildings.json",
        "contract": data_dir / "dataset_contract.json",
        "departments": data_dir / "departments.json",
        "places": data_dir / "places.json",
        "people": data_dir / "people.json",
        "report": data_dir / "report.json",
    }


def _snapshot_baseline_rows(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    paths = _dataset_paths(data_dir)
    return {
        dataset_name: _load_json_array(path)
        for dataset_name, path in paths.items()
        if dataset_name in BASELINE_PRESERVED_DATASETS
    }


def _seed_data_dir(data_dir: Path, seed_from: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    target_paths = _dataset_paths(data_dir)
    for dataset_name, source_path in _dataset_paths(seed_from).items():
        if not source_path.exists():
            continue
        target_path = target_paths.get(dataset_name)
        if target_path is None:
            continue
        shutil.copy2(source_path, target_path)


def _merge_rows_by_id(
    existing_rows: list[dict[str, Any]],
    refreshed_rows: list[dict[str, Any]],
    *,
    id_field: str,
) -> list[dict[str, Any]]:
    merged_by_id: dict[str, dict[str, Any]] = {}

    for row in existing_rows:
        row_id = row.get(id_field)
        if isinstance(row_id, str) and row_id:
            merged_by_id[row_id] = dict(row)

    for row in refreshed_rows:
        row_id = row.get(id_field)
        if not isinstance(row_id, str) or not row_id:
            continue
        merged = dict(merged_by_id.get(row_id, {}))
        merged.update(row)
        merged_by_id[row_id] = merged

    return sorted(merged_by_id.values(), key=lambda item: str(item.get(id_field, "")))


def _preserve_dataset_rows(
    dataset_name: str,
    *,
    baseline_rows: dict[str, list[dict[str, Any]]],
    data_dir: Path,
) -> None:
    id_field = BASELINE_PRESERVED_DATASETS[dataset_name]
    target_path = _dataset_paths(data_dir)[dataset_name]
    current_rows = _load_json_array(target_path)
    preserved_rows = _merge_rows_by_id(
        existing_rows=baseline_rows[dataset_name],
        refreshed_rows=current_rows,
        id_field=id_field,
    )
    write_json(target_path, preserved_rows)


def _invoke_command(command: Any, **kwargs: Any) -> None:
    callback = getattr(command, "callback", command)
    callback(**kwargs)


@click.group()
def cli() -> None:
    """UNICAL data extraction, normalization, and validation CLI."""


@cli.group()
def crawl() -> None:
    """Extract data from UNICAL public sources."""


@cli.group()
def link() -> None:
    """Link normalized datasets through deterministic references."""


@cli.group()
def corrections() -> None:
    """Apply manual correction registry to canonical datasets."""


@crawl.command("teachers")
@click.option(
    "--base-url",
    default=DEFAULT_TEACHERS_BASE_URL,
    show_default=True,
    help="Entry URL used to discover teacher pages.",
)
@click.option(
    "--out-file",
    default=str(DEFAULT_DATA_DIR / "people.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path where normalized people dataset will be written.",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Optional cache dir for HTML snapshots.",
)
@click.option(
    "--departments-file",
    default=str(DEFAULT_DATA_DIR / "departments.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Departments dataset used to resolve teacher department_id values.",
)
@click.option(
    "--places-file",
    default=str(DEFAULT_DATA_DIR / "places.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Places dataset where extracted teacher offices are upserted.",
)
@click.option(
    "--buildings-file",
    default=str(DEFAULT_DATA_DIR / "buildings.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Buildings dataset used to infer office building_id.",
)
@click.option("--rate-limit", default=0.5, show_default=True, type=float)
@click.option("--user-agent", default=DEFAULT_USER_AGENT, show_default=True)
@click.option("--max-retries", default=2, show_default=True, type=int)
@click.option("--retry-backoff", default=0.5, show_default=True, type=float)
@click.option("--timeout", "timeout_seconds", default=30.0, show_default=True, type=float)
@click.option("--failure-budget", default=0, show_default=True, type=int)
@click.option("--detail-enrichment/--no-detail-enrichment", default=True, show_default=True)
@click.option("--department-fallback/--no-department-fallback", default=True, show_default=True)
@click.option("--department-max-pages", default=10, show_default=True, type=int)
def crawl_teachers_command(
    base_url: str,
    out_file: Path,
    cache_dir: Path | None,
    departments_file: Path,
    places_file: Path,
    buildings_file: Path,
    rate_limit: float,
    user_agent: str,
    max_retries: int,
    retry_backoff: float,
    timeout_seconds: float,
    failure_budget: int,
    detail_enrichment: bool,
    department_fallback: bool,
    department_max_pages: int,
) -> None:
    """Crawl professor pages and write normalized `people.json`."""
    cache = HtmlCache(cache_dir) if cache_dir else None
    departments = _load_json_array(departments_file)

    with HttpClient(
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
        rate_limit_seconds=rate_limit,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff,
    ) as client:
        raw_teachers = crawl_teachers(
            base_url=base_url,
            client=client,
            cache=cache,
            detail_enrichment=detail_enrichment,
            progress_reporter=lambda message: click.echo(f"[teachers] {message}"),
        )
        if department_fallback:
            click.echo("[teachers] department fallback: start")
            department_teacher_map = crawl_department_teacher_map(
                departments=departments,
                client=client,
                cache=cache,
                max_pages_per_department=department_max_pages,
                progress_reporter=lambda message: click.echo(f"[teachers] {message}"),
            )
        else:
            click.echo("[teachers] department fallback: disabled")
            department_teacher_map = {}
        http_summary = _emit_http_diagnostics(client)

    _record_scrape_diagnostics(
        data_dir=out_file.parent,
        source_id="unical-teachers",
        summary=http_summary,
        failure_budget=failure_budget,
    )
    _enforce_failure_budget(
        source_id="unical-teachers",
        summary=http_summary,
        failure_budget=failure_budget,
    )

    buildings = _load_json_array(buildings_file)
    existing_places = _load_json_array(places_file)

    people = normalize_teachers(
        raw_teachers,
        departments=departments,
        department_teacher_map=department_teacher_map,
    )
    teacher_office_places = normalize_teacher_office_places(
        raw_teachers=raw_teachers,
        existing_places=existing_places,
        buildings=buildings,
    )
    write_json(out_file, people)
    write_json(places_file, teacher_office_places)

    sources_file = out_file.parent / "sources.json"
    source_entry = {
        "source_id": "unical-teachers",
        "name": "UNICAL Teachers Directory",
        "base_url": base_url,
        "notes": "Generated by unical_scraper crawl teachers",
        "last_crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    _upsert_source_entry(sources_file=sources_file, source_entry=source_entry)
    _apply_manual_corrections_for_paths([out_file, places_file, sources_file])

    click.echo(f"Crawled {len(raw_teachers)} teachers")
    click.echo(f"Department teacher fallback keys: {len(department_teacher_map)}")
    click.echo(f"Teacher office places: {len(teacher_office_places)}")
    click.echo(f"Wrote: {out_file}")
    click.echo(f"Wrote: {places_file}")
    click.echo(f"Wrote: {sources_file}")


@crawl.command("departments")
@click.option(
    "--base-url",
    default=DEFAULT_DEPARTMENTS_BASE_URL,
    show_default=True,
    help="Departments page URL.",
)
@click.option(
    "--out-file",
    default=str(DEFAULT_DATA_DIR / "departments.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path where normalized departments dataset will be written.",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Optional cache dir for HTML snapshots.",
)
@click.option("--rate-limit", default=0.5, show_default=True, type=float)
@click.option("--user-agent", default=DEFAULT_USER_AGENT, show_default=True)
@click.option("--max-retries", default=2, show_default=True, type=int)
@click.option("--retry-backoff", default=0.5, show_default=True, type=float)
@click.option("--failure-budget", default=0, show_default=True, type=int)
def crawl_departments_command(
    base_url: str,
    out_file: Path,
    cache_dir: Path | None,
    rate_limit: float,
    user_agent: str,
    max_retries: int,
    retry_backoff: float,
    failure_budget: int,
) -> None:
    """Crawl department pages and write normalized `departments.json`."""
    cache = HtmlCache(cache_dir) if cache_dir else None

    with HttpClient(
        user_agent=user_agent,
        rate_limit_seconds=rate_limit,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff,
    ) as client:
        raw_departments = crawl_departments(base_url=base_url, client=client, cache=cache)
        http_summary = _emit_http_diagnostics(client)

    _record_scrape_diagnostics(
        data_dir=out_file.parent,
        source_id="unical-departments",
        summary=http_summary,
        failure_budget=failure_budget,
    )
    _enforce_failure_budget(
        source_id="unical-departments",
        summary=http_summary,
        failure_budget=failure_budget,
    )

    departments = normalize_departments(raw_departments)
    write_json(out_file, departments)

    sources_file = out_file.parent / "sources.json"
    source_entry = {
        "source_id": "unical-departments",
        "name": "UNICAL Departments",
        "base_url": base_url,
        "notes": "Generated by unical_scraper crawl departments",
        "last_crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    _upsert_source_entry(sources_file=sources_file, source_entry=source_entry)
    _apply_manual_corrections_for_paths([out_file, sources_file])

    click.echo(f"Crawled {len(raw_departments)} departments")
    click.echo(f"Wrote: {out_file}")
    click.echo(f"Wrote: {sources_file}")


@crawl.command("services")
@click.option(
    "--base-url",
    required=True,
    help="Services page URL.",
)
@click.option(
    "--out-file",
    default=str(DEFAULT_DATA_DIR / "places.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path where normalized places dataset will be written.",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Optional cache dir for HTML snapshots.",
)
@click.option("--rate-limit", default=0.5, show_default=True, type=float)
@click.option("--user-agent", default=DEFAULT_USER_AGENT, show_default=True)
@click.option("--max-retries", default=2, show_default=True, type=int)
@click.option("--retry-backoff", default=0.5, show_default=True, type=float)
@click.option("--failure-budget", default=0, show_default=True, type=int)
def crawl_services_command(
    base_url: str,
    out_file: Path,
    cache_dir: Path | None,
    rate_limit: float,
    user_agent: str,
    max_retries: int,
    retry_backoff: float,
    failure_budget: int,
) -> None:
    """Crawl service pages and write normalized `places.json`."""
    cache = HtmlCache(cache_dir) if cache_dir else None

    with HttpClient(
        user_agent=user_agent,
        rate_limit_seconds=rate_limit,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff,
    ) as client:
        raw_services = crawl_services(base_url=base_url, client=client, cache=cache)
        http_summary = _emit_http_diagnostics(client)

    _record_scrape_diagnostics(
        data_dir=out_file.parent,
        source_id="unical-services",
        summary=http_summary,
        failure_budget=failure_budget,
    )
    _enforce_failure_budget(
        source_id="unical-services",
        summary=http_summary,
        failure_budget=failure_budget,
    )

    places = normalize_services(raw_services)
    write_json(out_file, places)

    sources_file = out_file.parent / "sources.json"
    source_entry = {
        "source_id": "unical-services",
        "name": "UNICAL Services",
        "base_url": base_url,
        "notes": "Generated by unical_scraper crawl services",
        "last_crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    _upsert_source_entry(sources_file=sources_file, source_entry=source_entry)
    _apply_manual_corrections_for_paths([out_file, sources_file])

    click.echo(f"Crawled {len(raw_services)} services")
    click.echo(f"Wrote: {out_file}")
    click.echo(f"Wrote: {sources_file}")


@crawl.command("buildings")
@click.option(
    "--base-url",
    default=DEFAULT_BUILDINGS_BASE_URL,
    show_default=True,
    help="Campus map page URL.",
)
@click.option(
    "--out-file",
    default=str(DEFAULT_DATA_DIR / "buildings.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path where normalized buildings dataset will be written.",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Optional cache dir for HTML snapshots.",
)
@click.option("--rate-limit", default=0.5, show_default=True, type=float)
@click.option("--user-agent", default=DEFAULT_USER_AGENT, show_default=True)
@click.option("--max-retries", default=2, show_default=True, type=int)
@click.option("--retry-backoff", default=0.5, show_default=True, type=float)
@click.option("--failure-budget", default=0, show_default=True, type=int)
def crawl_buildings_command(
    base_url: str,
    out_file: Path,
    cache_dir: Path | None,
    rate_limit: float,
    user_agent: str,
    max_retries: int,
    retry_backoff: float,
    failure_budget: int,
) -> None:
    """Crawl campus buildings and write normalized `buildings.json`."""
    cache = HtmlCache(cache_dir) if cache_dir else None

    with HttpClient(
        user_agent=user_agent,
        rate_limit_seconds=rate_limit,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff,
    ) as client:
        raw_buildings = crawl_buildings(base_url=base_url, client=client, cache=cache)
        http_summary = _emit_http_diagnostics(client)

    _record_scrape_diagnostics(
        data_dir=out_file.parent,
        source_id="unical-campus-map",
        summary=http_summary,
        failure_budget=failure_budget,
    )
    _enforce_failure_budget(
        source_id="unical-campus-map",
        summary=http_summary,
        failure_budget=failure_budget,
    )

    buildings = normalize_buildings(raw_buildings)
    write_json(out_file, buildings)

    sources_file = out_file.parent / "sources.json"
    source_entry = {
        "source_id": "unical-campus-map",
        "name": "UNICAL Campus Map",
        "base_url": base_url,
        "notes": "Generated by unical_scraper crawl buildings",
        "last_crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    _upsert_source_entry(sources_file=sources_file, source_entry=source_entry)
    _apply_manual_corrections_for_paths([out_file, sources_file])

    click.echo(f"Crawled {len(raw_buildings)} buildings")
    click.echo(f"Wrote: {out_file}")
    click.echo(f"Wrote: {sources_file}")


@crawl.command("aulas")
@click.option(
    "--base-url",
    default=DEFAULT_AULAS_BASE_URL,
    show_default=True,
    help="Campus map page URL used for aula discovery.",
)
@click.option(
    "--aulas-file",
    default=str(DEFAULT_DATA_DIR / "aulas.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path where normalized aulas dataset will be written.",
)
@click.option(
    "--places-file",
    default=str(DEFAULT_DATA_DIR / "places.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path where AULA place records will be upserted.",
)
@click.option(
    "--buildings-file",
    default=str(DEFAULT_DATA_DIR / "buildings.json"),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path to buildings dataset used for aula-to-building linking.",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Optional cache dir for HTML snapshots.",
)
@click.option("--rate-limit", default=0.5, show_default=True, type=float)
@click.option("--user-agent", default=DEFAULT_USER_AGENT, show_default=True)
@click.option("--max-retries", default=2, show_default=True, type=int)
@click.option("--retry-backoff", default=0.5, show_default=True, type=float)
@click.option("--timeout", "timeout_seconds", default=30.0, show_default=True, type=float)
@click.option("--failure-budget", default=0, show_default=True, type=int)
@click.option("--planner-discovery/--no-planner-discovery", default=True, show_default=True)
@click.option("--planner-public-links/--no-planner-public-links", default=True, show_default=True)
@click.option("--planner-impegni/--no-planner-impegni", default=True, show_default=True)
@click.option(
    "--planner-max-link-ids",
    default=None,
    type=int,
    help="Optional deterministic cap for planner public calendar link IDs.",
)
def crawl_aulas_command(
    base_url: str,
    aulas_file: Path,
    places_file: Path,
    buildings_file: Path,
    cache_dir: Path | None,
    rate_limit: float,
    user_agent: str,
    max_retries: int,
    retry_backoff: float,
    timeout_seconds: float,
    failure_budget: int,
    planner_discovery: bool,
    planner_public_links: bool,
    planner_impegni: bool,
    planner_max_link_ids: int | None,
) -> None:
    """Crawl aulas and write both `aulas.json` and AULA records in `places.json`."""
    cache = HtmlCache(cache_dir) if cache_dir else None

    with HttpClient(
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
        rate_limit_seconds=rate_limit,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff,
    ) as client:
        raw_aulas = crawl_aulas(
            base_url=base_url,
            client=client,
            cache=cache,
            planner_enable_discovery=planner_discovery,
            planner_enable_public_links=planner_public_links,
            planner_enable_impegni=planner_impegni,
            planner_max_link_ids=planner_max_link_ids,
            progress_reporter=lambda message: click.echo(f"[aulas] {message}"),
        )
        http_summary = _emit_http_diagnostics(client)

    _record_scrape_diagnostics(
        data_dir=aulas_file.parent,
        source_id="unical-aulas",
        summary=http_summary,
        failure_budget=failure_budget,
    )
    _enforce_failure_budget(
        source_id="unical-aulas",
        summary=http_summary,
        failure_budget=failure_budget,
    )

    buildings = _load_json_array(buildings_file)
    aulas, aula_places = normalize_aulas(raw_aulas=raw_aulas, buildings=buildings)
    write_json(aulas_file, aulas)

    existing_places = _load_json_array(places_file)
    merged_places = _merge_places_with_aulas(existing_places=existing_places, aula_places=aula_places)
    write_json(places_file, merged_places)

    sources_file = aulas_file.parent / "sources.json"
    source_entry = {
        "source_id": "unical-aulas",
        "name": "UNICAL Aula Map",
        "base_url": base_url,
        "notes": "Generated by unical_scraper crawl aulas",
        "last_crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    _upsert_source_entry(sources_file=sources_file, source_entry=source_entry)
    _apply_manual_corrections_for_paths([aulas_file, places_file, sources_file])

    click.echo(f"Crawled raw aulas: {len(raw_aulas)}")
    click.echo(f"Normalized aulas: {len(aulas)}")
    click.echo(f"Upserted AULA places: {len(aula_places)}")
    click.echo(f"Wrote: {aulas_file}")
    click.echo(f"Wrote: {places_file}")
    click.echo(f"Wrote: {sources_file}")


@crawl.command("full")
@click.option(
    "--data-dir",
    default=str(DEFAULT_DATA_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Output dir for normalized replay datasets.",
)
@click.option(
    "--schemas-dir",
    default=str(DEFAULT_SCHEMAS_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
    help="Schema dir used by trailing validate/report steps.",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Optional shared cache dir for replay requests.",
)
@click.option(
    "--seed-from",
    default=None,
    type=click.Path(path_type=Path),
    help="Optional baseline dataset dir copied into --data-dir before replay.",
)
@click.option(
    "--profile",
    default="fast",
    show_default=True,
    type=click.Choice(sorted(FULL_CRAWL_PROFILES.keys()), case_sensitive=False),
    help="Replay profile balancing reliability vs coverage breadth.",
)
@click.option("--rate-limit", default=0.5, show_default=True, type=float)
@click.option("--user-agent", default=DEFAULT_USER_AGENT, show_default=True)
@click.option("--max-retries", default=2, show_default=True, type=int)
@click.option("--retry-backoff", default=0.5, show_default=True, type=float)
@click.option(
    "--allow-canonical-write",
    is_flag=True,
    help="Allow writing full-crawl output into the canonical data/normalized dir.",
)
def crawl_full_command(
    data_dir: Path,
    schemas_dir: Path,
    cache_dir: Path | None,
    seed_from: Path | None,
    profile: str,
    rate_limit: float,
    user_agent: str,
    max_retries: int,
    retry_backoff: float,
    allow_canonical_write: bool,
) -> None:
    """Run the full scraper replay sequence into one target data dir."""
    if _is_canonical_data_dir(data_dir) and not allow_canonical_write:
        raise SystemExit(
            "crawl full refuses canonical writes by default; "
            "use --data-dir /tmp/... for hot tests or add --allow-canonical-write"
        )

    if seed_from is not None and seed_from.resolve() == data_dir.resolve():
        raise SystemExit("--seed-from must differ from --data-dir")

    baseline_source_dir = seed_from or data_dir
    baseline_rows = _snapshot_baseline_rows(baseline_source_dir)
    if seed_from is not None:
        _seed_data_dir(data_dir=data_dir, seed_from=seed_from)

    selected_profile = FULL_CRAWL_PROFILES[profile.lower()]
    paths = _dataset_paths(data_dir)
    _ensure_static_dataset_placeholders(data_dir)

    click.echo(f"[crawl full] profile={profile.lower()} data_dir={data_dir}")
    if seed_from is not None:
        click.echo(f"[crawl full] seed_from={seed_from}")

    click.echo("[crawl full] step=departments")
    _invoke_command(
        crawl_departments_command,
        base_url=DEFAULT_DEPARTMENTS_BASE_URL,
        out_file=paths["departments"],
        cache_dir=cache_dir,
        rate_limit=rate_limit,
        user_agent=user_agent,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        failure_budget=0,
    )
    _preserve_dataset_rows("departments", baseline_rows=baseline_rows, data_dir=data_dir)

    click.echo("[crawl full] step=buildings")
    _invoke_command(
        crawl_buildings_command,
        base_url=DEFAULT_BUILDINGS_BASE_URL,
        out_file=paths["buildings"],
        cache_dir=cache_dir,
        rate_limit=rate_limit,
        user_agent=user_agent,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        failure_budget=0,
    )
    _preserve_dataset_rows("buildings", baseline_rows=baseline_rows, data_dir=data_dir)

    click.echo("[crawl full] step=services")
    _invoke_command(
        crawl_services_command,
        base_url=DEFAULT_SERVICES_BASE_URL,
        out_file=paths["places"],
        cache_dir=cache_dir,
        rate_limit=rate_limit,
        user_agent=user_agent,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        failure_budget=selected_profile.services_failure_budget,
    )

    click.echo("[crawl full] step=teachers")
    if selected_profile.teachers_enabled:
        _invoke_command(
            crawl_teachers_command,
            base_url=DEFAULT_TEACHERS_BASE_URL,
            out_file=paths["people"],
            cache_dir=cache_dir,
            departments_file=paths["departments"],
            places_file=paths["places"],
            buildings_file=paths["buildings"],
            rate_limit=rate_limit,
            user_agent=user_agent,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            timeout_seconds=selected_profile.teachers_timeout_seconds,
            failure_budget=selected_profile.teachers_failure_budget,
            detail_enrichment=selected_profile.teachers_detail_enrichment,
            department_fallback=selected_profile.teachers_department_fallback,
            department_max_pages=10,
        )
        _preserve_dataset_rows("people", baseline_rows=baseline_rows, data_dir=data_dir)
        _preserve_dataset_rows("places", baseline_rows=baseline_rows, data_dir=data_dir)
    else:
        click.echo("[crawl full] step=teachers skipped by profile")

    click.echo("[crawl full] step=aulas")
    _invoke_command(
        crawl_aulas_command,
        base_url=DEFAULT_AULAS_BASE_URL,
        aulas_file=paths["aulas"],
        places_file=paths["places"],
        buildings_file=paths["buildings"],
        cache_dir=cache_dir,
        rate_limit=rate_limit,
        user_agent=user_agent,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        timeout_seconds=selected_profile.aulas_timeout_seconds,
        failure_budget=selected_profile.aulas_failure_budget,
        planner_discovery=selected_profile.aulas_planner_discovery,
        planner_public_links=selected_profile.aulas_planner_public_links,
        planner_impegni=selected_profile.aulas_planner_impegni,
        planner_max_link_ids=selected_profile.aulas_planner_max_link_ids,
    )
    _preserve_dataset_rows("aulas", baseline_rows=baseline_rows, data_dir=data_dir)
    _preserve_dataset_rows("places", baseline_rows=baseline_rows, data_dir=data_dir)

    click.echo("[crawl full] step=link places-buildings")
    _invoke_command(
        link_places_buildings_command,
        places_file=paths["places"],
        buildings_file=paths["buildings"],
    )

    click.echo("[crawl full] step=link aliases")
    _invoke_command(
        link_aliases_command,
        aulas_file=paths["aulas"],
        places_file=paths["places"],
        buildings_file=paths["buildings"],
        out_file=paths["aliases"],
    )

    click.echo("[crawl full] step=contract")
    _invoke_command(
        contract_command,
        data_dir=data_dir,
        out=paths["contract"],
        compatibility_version=DEFAULT_CONTRACT_COMPATIBILITY_VERSION,
        contract_version=DEFAULT_CONTRACT_VERSION,
    )

    click.echo("[crawl full] step=validate")
    _invoke_command(
        validate_command,
        data_dir=data_dir,
        schemas_dir=schemas_dir,
        verbose=False,
    )

    click.echo("[crawl full] step=report")
    _invoke_command(
        report_command,
        data_dir=data_dir,
        schemas_dir=schemas_dir,
        out=paths["report"],
    )

    click.echo("[crawl full] complete")


@link.command("places-buildings")
@click.option(
    "--places-file",
    default=str(DEFAULT_DATA_DIR / "places.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--buildings-file",
    default=str(DEFAULT_DATA_DIR / "buildings.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
def link_places_buildings_command(places_file: Path, buildings_file: Path) -> None:
    """Link `places.json` entries to `building_id` where inferable."""
    places = _load_json_array(places_file)
    buildings = _load_json_array(buildings_file)

    linked_places = link_places_to_buildings(places=places, buildings=buildings)
    linked_count = sum(1 for place in linked_places if place.get("building_id"))

    write_json(places_file, linked_places)
    _apply_manual_corrections_for_paths([places_file])
    click.echo(f"Linked places with building_id: {linked_count}/{len(linked_places)}")
    click.echo(f"Wrote: {places_file}")


@link.command("aliases")
@click.option(
    "--aulas-file",
    default=str(DEFAULT_DATA_DIR / "aulas.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--places-file",
    default=str(DEFAULT_DATA_DIR / "places.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--buildings-file",
    default=str(DEFAULT_DATA_DIR / "buildings.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--out-file",
    default=str(DEFAULT_DATA_DIR / "aliases.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
def link_aliases_command(
    aulas_file: Path,
    places_file: Path,
    buildings_file: Path,
    out_file: Path,
) -> None:
    """Generate deterministic aliases for aulas and landmark labels."""
    aulas = _load_json_array(aulas_file)
    places = _load_json_array(places_file)
    buildings = _load_json_array(buildings_file)
    aliases = build_search_aliases(aulas=aulas, places=places, buildings=buildings)
    write_json(out_file, aliases)
    _apply_manual_corrections_for_paths([out_file])

    click.echo(f"Generated aliases: {len(aliases)}")
    click.echo(f"Wrote: {out_file}")


@corrections.command("apply")
@click.option(
    "--data-dir",
    default=str(DEFAULT_DATA_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--registry-file",
    default=str(DEFAULT_CORRECTIONS_FILE),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--allowlist-file",
    default=str(DEFAULT_DESTRUCTIVE_ALLOWLIST_FILE),
    show_default=True,
    type=click.Path(path_type=Path),
)
def corrections_apply_command(
    data_dir: Path,
    registry_file: Path,
    allowlist_file: Path,
) -> None:
    """Apply approved manual corrections to canonical normalized datasets."""
    try:
        summary = apply_manual_corrections_to_data_dir(
            data_dir=data_dir,
            registry_path=registry_file,
            allowlist_path=allowlist_file,
            dataset_names=None,
        )
    except ManualCorrectionsError as exc:
        raise SystemExit(f"manual corrections failed: {exc}") from exc

    click.echo(
        "Manual corrections complete: "
        f"datasets={len(summary.datasets_scanned)} "
        f"rules_considered={summary.rules_considered} "
        f"rules_applied={summary.rules_applied} "
        f"field_changes={summary.fields_changed}"
    )


@cli.command("validate")
@click.option(
    "--data-dir",
    default=str(DEFAULT_DATA_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--schemas-dir",
    default=str(DEFAULT_SCHEMAS_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option("--verbose", is_flag=True, help="Print individual validation issues.")
def validate_command(data_dir: Path, schemas_dir: Path, verbose: bool) -> None:
    """Validate JSON datasets against schema and referential integrity."""
    schema_results = validate_dataset_dir(data_dir=data_dir, schemas_dir=schemas_dir)
    integrity_issues = check_integrity(data_dir=data_dir)

    invalid_schema_files = 0
    for dataset_name, errors in schema_results.items():
        status = "OK" if not errors else "INVALID"
        click.echo(f"[{status}] {dataset_name}")
        if errors:
            invalid_schema_files += 1
            if verbose:
                for error in errors:
                    click.echo(f"  - {error}")

    if integrity_issues:
        click.echo("[INTEGRITY] Issues found")
        for issue in integrity_issues:
            click.echo(f"  - ({issue.level}) {issue.file}: {issue.message}")
    else:
        click.echo("[INTEGRITY] OK")

    error_integrity_count = sum(1 for issue in integrity_issues if issue.level == "error")
    if invalid_schema_files > 0 or error_integrity_count > 0:
        raise SystemExit(1)


@cli.command("report")
@click.option(
    "--data-dir",
    default=str(DEFAULT_DATA_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--schemas-dir",
    default=str(DEFAULT_SCHEMAS_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--out",
    default=str(DEFAULT_DATA_DIR / "report.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
def report_command(data_dir: Path, schemas_dir: Path, out: Path) -> None:
    """Build a deterministic coverage + validation report JSON."""
    schema_results = validate_dataset_dir(data_dir=data_dir, schemas_dir=schemas_dir)
    integrity_issues = check_integrity(data_dir=data_dir)

    report_payload = build_coverage_report(
        data_dir=data_dir,
        schema_results=schema_results,
        integrity_issues=issues_to_dicts(integrity_issues),
    )
    write_json(out, report_payload)
    click.echo(f"Wrote report: {out}")


@cli.command("contract")
@click.option(
    "--data-dir",
    default=str(DEFAULT_DATA_DIR),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--out",
    default=str(DEFAULT_DATA_DIR / "dataset_contract.json"),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--compatibility-version",
    default=DEFAULT_CONTRACT_COMPATIBILITY_VERSION,
    show_default=True,
    type=int,
    help="Bump only on breaking data-contract changes expected by app clients.",
)
@click.option(
    "--contract-version",
    default=DEFAULT_CONTRACT_VERSION,
    show_default=True,
    help="Semantic version of the contract manifest format.",
)
def contract_command(
    data_dir: Path,
    out: Path,
    compatibility_version: int,
    contract_version: str,
) -> None:
    """Build deterministic dataset contract/version manifest JSON."""
    contract_payload = build_dataset_contract(
        data_dir=data_dir,
        compatibility_version=compatibility_version,
        contract_version=contract_version,
    )
    write_json(out, contract_payload)
    click.echo(f"Wrote contract: {out}")
