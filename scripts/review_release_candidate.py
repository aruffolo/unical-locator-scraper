#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DATASETS: dict[str, str] = {
    "buildings.json": "building_id",
    "places.json": "place_id",
    "people.json": "person_id",
    "aulas.json": "place_id",
    "departments.json": "department_id",
    "aliases.json": "alias_id",
}

LOCKED_ENTITY_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("buildings.json", "building_id", "cappella-universitaria"),
    ("buildings.json", "building_id", "cubo-20"),
    ("places.json", "place_id", "office-ufficio-cubo-0-c-primo-piano"),
    ("places.json", "place_id", "office-ufficio-cubo-4c-piano-3"),
    ("places.json", "place_id", "service-centro-sportivo"),
    ("people.json", "person_id", "francesco-scarcello"),
)

SHARED_FIELD_IGNORES = {"last_verified_at"}
SAMPLE_LIMIT = 15
NEW_PEOPLE_SAMPLE_LIMIT = 25


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _index_rows(rows: list[dict[str, Any]], id_field: str) -> dict[str, dict[str, Any]]:
    return {
        str(row[id_field]): row
        for row in rows
        if isinstance(row.get(id_field), str) and str(row[id_field])
    }


def _is_empty_value(value: Any) -> bool:
    return value in (None, "", [], {})


def _render_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _summarize_dataset(
    baseline_dir: Path,
    candidate_dir: Path,
    dataset_name: str,
    id_field: str,
) -> dict[str, Any]:
    baseline_rows = _load_rows(baseline_dir / dataset_name)
    candidate_rows = _load_rows(candidate_dir / dataset_name)
    baseline = _index_rows(baseline_rows, id_field)
    candidate = _index_rows(candidate_rows, id_field)

    baseline_ids = set(baseline)
    candidate_ids = set(candidate)
    shared_ids = sorted(baseline_ids & candidate_ids)
    removed_ids = sorted(baseline_ids - candidate_ids)
    added_ids = sorted(candidate_ids - baseline_ids)

    field_losses: list[dict[str, Any]] = []
    value_changes: list[dict[str, Any]] = []
    for entity_id in shared_ids:
        baseline_row = baseline[entity_id]
        candidate_row = candidate[entity_id]

        lost_fields: list[str] = []
        changed_fields: list[str] = []
        for field_name, baseline_value in baseline_row.items():
            if field_name in SHARED_FIELD_IGNORES:
                continue
            if field_name not in candidate_row:
                if not _is_empty_value(baseline_value):
                    lost_fields.append(field_name)
                continue
            candidate_value = candidate_row[field_name]
            if not _is_empty_value(baseline_value) and _is_empty_value(candidate_value):
                lost_fields.append(field_name)
            elif baseline_value != candidate_value:
                changed_fields.append(field_name)

        if lost_fields:
            field_losses.append({"entity_id": entity_id, "fields": lost_fields})
        if changed_fields:
            value_changes.append({"entity_id": entity_id, "fields": changed_fields})

    return {
        "dataset_name": dataset_name,
        "baseline_count": len(baseline),
        "candidate_count": len(candidate),
        "removed_ids": removed_ids,
        "added_ids": added_ids,
        "field_losses": field_losses,
        "value_changes": value_changes,
        "baseline": baseline,
        "candidate": candidate,
    }


def _summarize_people(baseline_dir: Path, candidate_dir: Path) -> dict[str, Any]:
    baseline = _index_rows(_load_rows(baseline_dir / "people.json"), "person_id")
    candidate = _index_rows(_load_rows(candidate_dir / "people.json"), "person_id")
    new_ids = sorted(set(candidate) - set(baseline))
    shared_ids = sorted(set(candidate) & set(baseline))

    new_rows = [candidate[person_id] for person_id in new_ids]
    return {
        "baseline_count": len(baseline),
        "candidate_count": len(candidate),
        "added_count": len(new_ids),
        "removed_count": len(set(baseline) - set(candidate)),
        "baseline_with_office": sum(1 for row in baseline.values() if row.get("office_place_id")),
        "candidate_with_office": sum(1 for row in candidate.values() if row.get("office_place_id")),
        "shared_with_office_before": sum(
            1 for person_id in shared_ids if baseline[person_id].get("office_place_id")
        ),
        "shared_with_office_after": sum(
            1 for person_id in shared_ids if candidate[person_id].get("office_place_id")
        ),
        "new_with_office": sum(1 for row in new_rows if row.get("office_place_id")),
        "new_with_email": sum(1 for row in new_rows if row.get("email")),
        "new_with_department": sum(1 for row in new_rows if row.get("department_id")),
        "new_source_counts": Counter(str(row.get("source_id")) for row in new_rows),
        "new_ids": new_ids,
        "candidate": candidate,
    }


def _format_dataset_section(summary: dict[str, Any]) -> list[str]:
    lines = [
        f"### {summary['dataset_name']}",
        (
            f"- baseline: {summary['baseline_count']}"
            f", candidate: {summary['candidate_count']}"
            f", removed: {len(summary['removed_ids'])}"
            f", added: {len(summary['added_ids'])}"
        ),
        f"- shared-entity field-loss count: {len(summary['field_losses'])}",
        f"- shared-entity value-change count: {len(summary['value_changes'])}",
    ]
    if summary["removed_ids"]:
        lines.append(f"- removed sample: {', '.join(summary['removed_ids'][:SAMPLE_LIMIT])}")
    if summary["added_ids"]:
        lines.append(f"- added sample: {', '.join(summary['added_ids'][:SAMPLE_LIMIT])}")
    if summary["field_losses"]:
        samples = []
        for item in summary["field_losses"][:SAMPLE_LIMIT]:
            samples.append(f"{item['entity_id']} -> {', '.join(item['fields'])}")
        lines.append(f"- field-loss sample: {'; '.join(samples)}")
    if summary["value_changes"]:
        samples = []
        for item in summary["value_changes"][:SAMPLE_LIMIT]:
            samples.append(f"{item['entity_id']} -> {', '.join(item['fields'])}")
        lines.append(f"- value-change sample: {'; '.join(samples)}")
    lines.append("")
    return lines


def _format_locked_checks(dataset_summaries: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["## Locked Entities"]
    for dataset_name, id_field, entity_id in LOCKED_ENTITY_CHECKS:
        candidate = dataset_summaries[dataset_name]["candidate"]
        status = "present" if entity_id in candidate else "missing"
        lines.append(f"- {dataset_name}:{entity_id} -> {status}")
    lines.append("")
    return lines


def _format_people_section(summary: dict[str, Any]) -> list[str]:
    lines = [
        "## People Delta",
        f"- baseline people: {summary['baseline_count']}",
        f"- candidate people: {summary['candidate_count']}",
        f"- added people: {summary['added_count']}",
        f"- removed people: {summary['removed_count']}",
        f"- baseline with office_place_id: {summary['baseline_with_office']}",
        f"- candidate with office_place_id: {summary['candidate_with_office']}",
        f"- shared with office_place_id before: {summary['shared_with_office_before']}",
        f"- shared with office_place_id after: {summary['shared_with_office_after']}",
        f"- new people with office_place_id: {summary['new_with_office']}",
        f"- new people with email: {summary['new_with_email']}",
        f"- new people with department_id: {summary['new_with_department']}",
        f"- new source_id counts: {dict(summary['new_source_counts'])}",
    ]
    if summary["new_ids"]:
        sample_lines = []
        for person_id in summary["new_ids"][:NEW_PEOPLE_SAMPLE_LIMIT]:
            row = summary["candidate"][person_id]
            sample_lines.append(
                (
                    f"{person_id} | {row.get('full_name')} | "
                    f"email={row.get('email')} | "
                    f"department_id={row.get('department_id')} | "
                    f"office_place_id={row.get('office_place_id')}"
                )
            )
        lines.append("- new people sample:")
        lines.extend(f"  - {line}" for line in sample_lines)
    lines.append("")
    return lines


def _format_changed_entity_details(dataset_summaries: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["## Shared Entity Changes"]
    for dataset_name in ("places.json", "aulas.json"):
        summary = dataset_summaries[dataset_name]
        if not summary["value_changes"]:
            lines.append(f"- {dataset_name}: none")
            continue
        lines.append(f"- {dataset_name}:")
        for item in summary["value_changes"][:SAMPLE_LIMIT]:
            entity_id = item["entity_id"]
            baseline_row = summary["baseline"][entity_id]
            candidate_row = summary["candidate"][entity_id]
            field_details = []
            for field_name in item["fields"]:
                field_details.append(
                    (
                        f"{field_name}: "
                        f"{_render_value(baseline_row.get(field_name))} -> "
                        f"{_render_value(candidate_row.get(field_name))}"
                    )
                )
            lines.append(f"  - {entity_id}")
            lines.extend(f"    - {detail}" for detail in field_details)
    lines.append("")
    return lines


def build_report(baseline_dir: Path, candidate_dir: Path) -> str:
    dataset_summaries = {
        dataset_name: _summarize_dataset(
            baseline_dir=baseline_dir,
            candidate_dir=candidate_dir,
            dataset_name=dataset_name,
            id_field=id_field,
        )
        for dataset_name, id_field in DATASETS.items()
    }
    people_summary = _summarize_people(baseline_dir=baseline_dir, candidate_dir=candidate_dir)

    lines = [
        "# Release Candidate Review",
        "",
        f"- baseline_dir: {baseline_dir}",
        f"- candidate_dir: {candidate_dir}",
        "",
    ]
    lines.extend(_format_locked_checks(dataset_summaries))
    lines.append("## Dataset Summary")
    lines.append("")
    for dataset_name in ("buildings.json", "places.json", "people.json", "aulas.json", "departments.json", "aliases.json"):
        lines.extend(_format_dataset_section(dataset_summaries[dataset_name]))
    lines.extend(_format_people_section(people_summary))
    lines.extend(_format_changed_entity_details(dataset_summaries))
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review a release candidate dataset against baseline.")
    parser.add_argument("--baseline-dir", required=True, type=Path)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None, help="Optional markdown report output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        baseline_dir=args.baseline_dir.resolve(),
        candidate_dir=args.candidate_dir.resolve(),
    )
    print(report, end="")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
