"""JSON Schema validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_json_file(data_path: Path, schema_path: Path) -> list[str]:
    """Validate one JSON file against one schema and return issue messages."""
    data = _load_json(data_path)
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema)

    messages: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda err: str(list(err.path))):
        location = "/".join(str(part) for part in error.path)
        pointer = f"/{location}" if location else "/"
        messages.append(f"{pointer}: {error.message}")

    return messages


def validate_dataset_dir(data_dir: Path, schemas_dir: Path) -> dict[str, list[str]]:
    """Validate every `*.schema.json` file against sibling `*.json` data files."""
    results: dict[str, list[str]] = {}

    for schema_path in sorted(schemas_dir.glob("*.schema.json")):
        dataset_name = schema_path.name.replace(".schema.json", ".json")
        data_path = data_dir / dataset_name
        if not data_path.exists():
            results[dataset_name] = [f"Missing dataset: {data_path}"]
            continue
        results[dataset_name] = validate_json_file(data_path=data_path, schema_path=schema_path)

    return results
