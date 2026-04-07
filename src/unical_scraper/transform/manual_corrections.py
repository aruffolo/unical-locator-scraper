"""Manual correction registry loading and conflict-resolution helpers."""

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


@dataclass(frozen=True)
class DestructiveAllowlist:
    """Rule IDs allowed to perform destructive changes."""

    version: int
    allowed_rule_ids: frozenset[str]


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

    target = CorrectionTarget(
        entity_type=_required_non_empty_string(raw_entry, "entity_type", index=index),
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

