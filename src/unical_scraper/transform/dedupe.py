"""Deduplication helpers for normalized records."""

from __future__ import annotations

from collections.abc import Iterable


Record = dict[str, object]


def dedupe_records(records: Iterable[Record], key_fields: tuple[str, ...]) -> list[Record]:
    """Deduplicate records preserving first occurrence."""
    seen: set[tuple[object, ...]] = set()
    output: list[Record] = []

    for record in records:
        key = tuple(record.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        output.append(record)

    return output


def dedupe_people(records: Iterable[Record]) -> list[Record]:
    """Deduplicate people primarily by `person_id`."""
    return dedupe_records(records, key_fields=("person_id",))
