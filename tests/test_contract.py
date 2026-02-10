from __future__ import annotations

import json
from pathlib import Path

from unical_scraper.validate.contract import CONTRACT_DATASETS, build_dataset_contract


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_dataset_contract_contains_expected_fields(tmp_path: Path) -> None:
    for name in CONTRACT_DATASETS:
        payload: object = [] if name.endswith(".json") else {}
        _write(tmp_path / name, payload)

    _write(
        tmp_path / "aulas.json",
        [
            {"aula_id": "a1", "building_id": "b1", "floor": "Piano Terra", "capacity": 80},
            {"aula_id": "a2"},
        ],
    )

    contract = build_dataset_contract(
        data_dir=tmp_path,
        compatibility_version=1,
        contract_version="1.0.0",
    )

    assert contract["contract_id"] == "unical-normalized-datasets"
    assert contract["contract_version"] == "1.0.0"
    assert contract["compatibility_version"] == 1
    assert len(contract["revision"]) == 64
    assert len(contract["datasets"]) == len(CONTRACT_DATASETS)

    aulas_cov = contract["coverage"]["aulas"]
    assert aulas_cov["total"] == 2
    assert aulas_cov["with_building_id"] == 1
    assert aulas_cov["with_floor"] == 1
    assert aulas_cov["with_capacity"] == 1


def test_build_dataset_contract_rejects_invalid_compatibility_version(tmp_path: Path) -> None:
    for name in CONTRACT_DATASETS:
        _write(tmp_path / name, [])

    try:
        build_dataset_contract(
            data_dir=tmp_path,
            compatibility_version=0,
            contract_version="1.0.0",
        )
    except ValueError as exc:
        assert "compatibility_version must be >= 1" in str(exc)
    else:
        raise AssertionError("expected ValueError for compatibility_version=0")
