"""Dataset contract/version manifest helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_DATASETS = (
    "aliases.json",
    "aulas.json",
    "building_entrances.json",
    "buildings.json",
    "departments.json",
    "faqs.json",
    "glossary.json",
    "people.json",
    "places.json",
    "sources.json",
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _dataset_records_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if payload is None:
        return 0
    return 1


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_dataset_contract(
    data_dir: Path,
    compatibility_version: int,
    contract_version: str,
) -> dict[str, Any]:
    """Build deterministic dataset contract metadata."""
    if compatibility_version < 1:
        raise ValueError("compatibility_version must be >= 1")

    datasets: list[dict[str, Any]] = []
    for dataset_name in CONTRACT_DATASETS:
        dataset_path = data_dir / dataset_name
        payload = _load_json(dataset_path)
        datasets.append(
            {
                "name": dataset_name,
                "records": _dataset_records_count(payload),
                "sha256": _sha256_file(dataset_path),
            }
        )

    aulas_payload = _load_json(data_dir / "aulas.json")
    aulas = [entry for entry in aulas_payload if isinstance(entry, dict)] if isinstance(aulas_payload, list) else []
    aulas_total = len(aulas)
    aulas_with_building = sum(1 for aula in aulas if isinstance(aula.get("building_id"), str) and aula.get("building_id"))
    aulas_with_floor = sum(1 for aula in aulas if isinstance(aula.get("floor"), str) and aula.get("floor"))
    aulas_with_capacity = sum(1 for aula in aulas if isinstance(aula.get("capacity"), int))

    revision_material = "\n".join(
        f"{item['name']}:{item['sha256']}:{item['records']}"
        for item in sorted(datasets, key=lambda entry: str(entry["name"]))
    )
    revision = hashlib.sha256(revision_material.encode("utf-8")).hexdigest()

    return {
        "contract_id": "unical-normalized-datasets",
        "contract_version": contract_version,
        "compatibility_version": compatibility_version,
        "revision": revision,
        "datasets": sorted(datasets, key=lambda entry: str(entry["name"])),
        "coverage": {
            "aulas": {
                "total": aulas_total,
                "with_building_id": aulas_with_building,
                "with_floor": aulas_with_floor,
                "with_capacity": aulas_with_capacity,
            }
        },
    }
