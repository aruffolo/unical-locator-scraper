"""Manual correction registry loading, validation, and application helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


VALID_ACTIONS = frozenset(
    {
        "set_null",
        "replace",
        "drop_if_matches",
        "drop_if_prefix",
        "override",
        "alias",
        "merge",
        "extract",
    }
)
VALID_STATUSES = frozenset({"draft", "review", "approved", "applied", "archived"})
APPLYABLE_STATUSES = frozenset({"approved", "applied"})
REVIEWER_REQUIRED_STATUSES = frozenset({"approved", "applied", "archived"})
DESTRUCTIVE_ACTIONS = frozenset({"set_null", "drop_if_matches", "drop_if_prefix"})

ENTITY_TO_DATASET: dict[str, tuple[str, str]] = {
    "alias": ("aliases.json", "alias_id"),
    "aula": ("aulas.json", "aula_id"),
    "building": ("buildings.json", "building_id"),
    "department": ("departments.json", "department_id"),
    "person": ("people.json", "person_id"),
    "place": ("places.json", "place_id"),
    "source": ("sources.json", "source_id"),
}
ENTITY_TYPE_ALIASES: dict[str, str] = {
    "alias": "alias",
    "aliases": "alias",
    "aula": "aula",
    "aulas": "aula",
    "building": "building",
    "buildings": "building",
    "department": "department",
    "departments": "department",
    "person": "person",
    "people": "person",
    "place": "place",
    "places": "place",
    "source": "source",
    "sources": "source",
}


class ManualCorrectionsError(ValueError):
    """Raised when correction-registry payloads are invalid."""


@dataclass(frozen=True)
class CorrectionTarget:
    """Exact selector for a single canonical field."""

    entity_type: str
    entity_id: str
    field: str

    def key(self) -> tuple[str, str, str]:
        return (self.entity_type, self.entity_id, self.field)


@dataclass(frozen=True)
class CorrectionRule:
    """Validated correction rule."""

    id: str
    action: str
    target: CorrectionTarget
    reason: str
    author: str
    created_at: str
    status: str
    reviewer: str | None
    priority: int
    params: dict[str, Any]


@dataclass(frozen=True)
class DestructiveAllowlist:
    """Rule IDs allowed to perform destructive changes."""

    version: int
    allowed_rule_ids: frozenset[str]


@dataclass(frozen=True)
class ApplySummary:
    """Outcome stats for a correction application run."""

    datasets_scanned: tuple[str, ...]
    rules_considered: int
    rules_applied: int
    fields_changed: int


def load_manual_corrections(path: Path) -> list[CorrectionRule]:
    """Load and validate manual-corrections registry."""
    payload = _load_json_compatible_yaml(path)
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise ManualCorrectionsError("manual_corrections.version must be an int >= 1")

    entries = payload.get("corrections")
    if not isinstance(entries, list):
        raise ManualCorrectionsError("manual_corrections.corrections must be a list")

    rules = [_parse_rule(entry, index) for index, entry in enumerate(entries)]
    _validate_unique_rule_ids(rules)
    _validate_conflict_priorities(rules)
    return rules


def apply_manual_corrections_to_data_dir(
    *,
    data_dir: Path,
    registry_path: Path,
    allowlist_path: Path,
    dataset_names: Iterable[str] | None = None,
) -> ApplySummary:
    """Apply approved corrections to normalized datasets in `data_dir`."""
    rules = load_manual_corrections(registry_path)
    allowlist = load_destructive_allowlist(allowlist_path)
    selected_names = (
        {name for name in dataset_names if name in _supported_dataset_names()}
        if dataset_names is not None
        else _supported_dataset_names()
    )
    if not selected_names:
        return ApplySummary(
            datasets_scanned=tuple(),
            rules_considered=0,
            rules_applied=0,
            fields_changed=0,
        )

    applyable_rules = [rule for rule in rules if rule.status in APPLYABLE_STATUSES]
    _validate_destructive_allowlist(
        rules=applyable_rules,
        allowlist=allowlist,
    )

    grouped = _group_rules_by_dataset(applyable_rules)
    changed_fields = 0
    applied_rules = 0
    scanned = sorted(selected_names)
    for dataset_name in scanned:
        rules_for_dataset = grouped.get(dataset_name, [])
        if not rules_for_dataset:
            continue
        dataset_path = data_dir / dataset_name
        rows = _load_dataset_rows(dataset_path)
        id_field = _dataset_id_field_for_name(dataset_name)
        selected_rules = _select_winning_rules(rules_for_dataset)
        changed, used = _apply_rules_to_rows(rows, id_field=id_field, rules=selected_rules)
        if changed > 0:
            _write_json(dataset_path, rows)
        changed_fields += changed
        applied_rules += used

    return ApplySummary(
        datasets_scanned=tuple(scanned),
        rules_considered=len(applyable_rules),
        rules_applied=applied_rules,
        fields_changed=changed_fields,
    )


def load_destructive_allowlist(path: Path) -> DestructiveAllowlist:
    """Load and validate destructive-change allowlist."""
    payload = _load_json_compatible_yaml(path)
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise ManualCorrectionsError("destructive_allowlist.version must be an int >= 1")

    raw_ids = payload.get("allowed_rule_ids")
    if not isinstance(raw_ids, list):
        raise ManualCorrectionsError("destructive_allowlist.allowed_rule_ids must be a list")

    rule_ids: list[str] = []
    for index, value in enumerate(raw_ids):
        if not isinstance(value, str) or not value.strip():
            raise ManualCorrectionsError(
                f"destructive_allowlist.allowed_rule_ids[{index}] must be a non-empty string"
            )
        rule_ids.append(value.strip())

    if len(rule_ids) != len(set(rule_ids)):
        raise ManualCorrectionsError("destructive_allowlist.allowed_rule_ids contains duplicates")

    return DestructiveAllowlist(version=version, allowed_rule_ids=frozenset(rule_ids))


def select_rule_for_target(
    rules: Iterable[CorrectionRule],
    target: CorrectionTarget,
) -> CorrectionRule | None:
    """Pick the applyable rule with highest priority for an exact target."""
    candidates = [
        rule
        for rule in rules
        if rule.status in APPLYABLE_STATUSES and rule.target.key() == target.key()
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item.priority, item.id))
    return candidates[0]


def _load_json_compatible_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ManualCorrectionsError(f"missing file: {path}")

    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManualCorrectionsError(
            f"{path} must be JSON-compatible YAML (JSON subset). parse error: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise ManualCorrectionsError(f"{path} root payload must be an object")
    return payload


def _parse_rule(raw_entry: object, index: int) -> CorrectionRule:
    if not isinstance(raw_entry, dict):
        raise ManualCorrectionsError(f"corrections[{index}] must be an object")

    rule_id = _required_non_empty_string(raw_entry, "id", index=index)
    action = _required_non_empty_string(raw_entry, "action", index=index)
    if action not in VALID_ACTIONS:
        raise ManualCorrectionsError(
            f"corrections[{index}].action must be one of: {sorted(VALID_ACTIONS)}"
        )

    normalized_entity_type = _normalize_entity_type(
        _required_non_empty_string(raw_entry, "entity_type", index=index),
        index=index,
    )
    target = CorrectionTarget(
        entity_type=normalized_entity_type,
        entity_id=_required_non_empty_string(raw_entry, "entity_id", index=index),
        field=_required_non_empty_string(raw_entry, "field", index=index),
    )

    reason = _required_non_empty_string(raw_entry, "reason", index=index)
    author = _required_non_empty_string(raw_entry, "author", index=index)
    created_at = _required_non_empty_string(raw_entry, "created_at", index=index)
    _validate_iso8601_with_timezone(created_at, f"corrections[{index}].created_at")

    status = _required_non_empty_string(raw_entry, "status", index=index)
    if status not in VALID_STATUSES:
        raise ManualCorrectionsError(
            f"corrections[{index}].status must be one of: {sorted(VALID_STATUSES)}"
        )

    reviewer_raw = raw_entry.get("reviewer")
    reviewer = None
    if reviewer_raw is not None:
        if not isinstance(reviewer_raw, str) or not reviewer_raw.strip():
            raise ManualCorrectionsError(
                f"corrections[{index}].reviewer must be a non-empty string when provided"
            )
        reviewer = reviewer_raw.strip()
    if status in REVIEWER_REQUIRED_STATUSES and reviewer is None:
        raise ManualCorrectionsError(
            f"corrections[{index}].reviewer is required when status is '{status}'"
        )

    priority_raw = raw_entry.get("priority", 0)
    if not isinstance(priority_raw, int):
        raise ManualCorrectionsError(f"corrections[{index}].priority must be an integer")

    known_keys = {
        "id",
        "action",
        "entity_type",
        "entity_id",
        "field",
        "reason",
        "author",
        "created_at",
        "status",
        "reviewer",
        "priority",
    }
    params = {
        key: value
        for key, value in raw_entry.items()
        if key not in known_keys
    }

    return CorrectionRule(
        id=rule_id,
        action=action,
        target=target,
        reason=reason,
        author=author,
        created_at=created_at,
        status=status,
        reviewer=reviewer,
        priority=priority_raw,
        params=params,
    )


def _required_non_empty_string(
    payload: dict[str, object],
    field_name: str,
    *,
    index: int,
) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ManualCorrectionsError(
            f"corrections[{index}].{field_name} must be a non-empty string"
        )
    return value.strip()


def _validate_iso8601_with_timezone(value: str, field_name: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManualCorrectionsError(f"{field_name} must be valid ISO8601") from exc
    if parsed.tzinfo is None:
        raise ManualCorrectionsError(f"{field_name} must include timezone info")


def _validate_unique_rule_ids(rules: list[CorrectionRule]) -> None:
    rule_ids = [rule.id for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise ManualCorrectionsError("manual_corrections has duplicate rule IDs")


def _validate_conflict_priorities(rules: list[CorrectionRule]) -> None:
    active_rules = [rule for rule in rules if rule.status != "archived"]
    grouped: dict[tuple[str, str, str], list[CorrectionRule]] = {}
    for rule in active_rules:
        grouped.setdefault(rule.target.key(), []).append(rule)

    for target_key, target_rules in grouped.items():
        if len(target_rules) < 2:
            continue
        by_priority: dict[int, int] = {}
        for rule in target_rules:
            by_priority[rule.priority] = by_priority.get(rule.priority, 0) + 1
        if any(count > 1 for count in by_priority.values()):
            raise ManualCorrectionsError(
                "ambiguous priority conflict for target "
                f"{target_key}: multiple active rules share the same priority"
            )


def _normalize_entity_type(entity_type: str, *, index: int) -> str:
    key = entity_type.strip().casefold()
    normalized = ENTITY_TYPE_ALIASES.get(key)
    if normalized is None:
        raise ManualCorrectionsError(
            f"corrections[{index}].entity_type must be one of: {sorted(ENTITY_TO_DATASET)}"
        )
    return normalized


def _supported_dataset_names() -> set[str]:
    return {dataset_name for dataset_name, _ in ENTITY_TO_DATASET.values()}


def _group_rules_by_dataset(
    rules: Iterable[CorrectionRule],
) -> dict[str, list[CorrectionRule]]:
    grouped: dict[str, list[CorrectionRule]] = {}
    for rule in rules:
        dataset_name, _ = ENTITY_TO_DATASET[rule.target.entity_type]
        grouped.setdefault(dataset_name, []).append(rule)
    return grouped


def _dataset_id_field_for_name(dataset_name: str) -> str:
    for mapped_dataset_name, id_field in ENTITY_TO_DATASET.values():
        if mapped_dataset_name == dataset_name:
            return id_field
    raise ManualCorrectionsError(f"unsupported dataset name: {dataset_name}")


def _load_dataset_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ManualCorrectionsError(f"dataset file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ManualCorrectionsError(f"dataset payload must be an array: {path}")
    rows = [row for row in payload if isinstance(row, dict)]
    if len(rows) != len(payload):
        raise ManualCorrectionsError(f"dataset contains non-object rows: {path}")
    return rows


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
        output.write("\n")


def _select_winning_rules(rules: Iterable[CorrectionRule]) -> list[CorrectionRule]:
    winners: dict[tuple[str, str, str], CorrectionRule] = {}
    for rule in rules:
        key = rule.target.key()
        current = winners.get(key)
        if current is None:
            winners[key] = rule
            continue
        if rule.priority > current.priority:
            winners[key] = rule
            continue
        if rule.priority == current.priority and rule.id < current.id:
            winners[key] = rule
    return list(winners.values())


def _apply_rules_to_rows(
    rows: list[dict[str, Any]],
    *,
    id_field: str,
    rules: list[CorrectionRule],
) -> tuple[int, int]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(id_field)
        if isinstance(value, str) and value:
            by_id[value] = row

    changed_fields = 0
    applied_rules = 0
    for rule in sorted(rules, key=lambda item: (-item.priority, item.id)):
        row = by_id.get(rule.target.entity_id)
        if row is None:
            continue
        current_value = row.get(rule.target.field)
        next_value, changed = _resolve_next_value(rule, current_value)
        if not changed:
            continue
        row[rule.target.field] = next_value
        changed_fields += 1
        applied_rules += 1
    return changed_fields, applied_rules


def _resolve_next_value(rule: CorrectionRule, current_value: Any) -> tuple[Any, bool]:
    if rule.action == "set_null":
        return (None, current_value is not None)
    if rule.action == "replace":
        replacement = _require_param(rule, "value")
        return (replacement, replacement != current_value)
    if rule.action == "override":
        replacement = _require_param(rule, "value")
        if current_value in (None, ""):
            return (replacement, replacement != current_value)
        return (current_value, False)
    if rule.action == "drop_if_matches":
        if not isinstance(current_value, str):
            return (current_value, False)
        patterns = _require_patterns(rule)
        lowered = current_value.strip().casefold()
        if any(lowered == pattern.casefold() for pattern in patterns):
            return (None, True)
        return (current_value, False)
    if rule.action == "drop_if_prefix":
        if not isinstance(current_value, str):
            return (current_value, False)
        patterns = _require_patterns(rule)
        lowered = current_value.strip().casefold()
        if any(lowered.startswith(pattern.casefold()) for pattern in patterns):
            return (None, True)
        return (current_value, False)
    raise ManualCorrectionsError(
        f"rule '{rule.id}' uses unsupported apply-time action '{rule.action}'"
    )


def _require_param(rule: CorrectionRule, key: str) -> Any:
    if key not in rule.params:
        raise ManualCorrectionsError(f"rule '{rule.id}' missing required param '{key}'")
    return rule.params[key]


def _require_patterns(rule: CorrectionRule) -> list[str]:
    raw_patterns = _require_param(rule, "patterns")
    if not isinstance(raw_patterns, list) or not raw_patterns:
        raise ManualCorrectionsError(
            f"rule '{rule.id}' param 'patterns' must be a non-empty list"
        )
    patterns: list[str] = []
    for index, value in enumerate(raw_patterns):
        if not isinstance(value, str) or not value.strip():
            raise ManualCorrectionsError(
                f"rule '{rule.id}' patterns[{index}] must be a non-empty string"
            )
        patterns.append(value.strip())
    return patterns


def _validate_destructive_allowlist(
    *,
    rules: Iterable[CorrectionRule],
    allowlist: DestructiveAllowlist,
) -> None:
    not_allowed = [
        rule.id
        for rule in rules
        if rule.action in DESTRUCTIVE_ACTIONS and rule.id not in allowlist.allowed_rule_ids
    ]
    if not_allowed:
        raise ManualCorrectionsError(
            "destructive rules must be allowlisted: " + ", ".join(sorted(not_allowed))
        )
