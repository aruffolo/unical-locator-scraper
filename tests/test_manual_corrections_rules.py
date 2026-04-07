from __future__ import annotations

import json
from pathlib import Path

import pytest

from unical_scraper.transform.manual_corrections import (
    CorrectionTarget,
    ManualCorrectionsError,
    load_destructive_allowlist,
    load_manual_corrections,
    select_rule_for_target,
)


def _write_payload(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_load_manual_corrections_accepts_json_compatible_yaml(tmp_path: Path) -> None:
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-001",
                    "action": "set_null",
                    "entity_type": "building",
                    "entity_id": "cappella-universitaria",
                    "field": "description",
                    "reason": "Remove boilerplate map text",
                    "author": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "draft",
                }
            ],
        },
    )

    rules = load_manual_corrections(registry_path)

    assert len(rules) == 1
    assert rules[0].id == "rule-001"
    assert rules[0].priority == 0


def test_load_manual_corrections_requires_reviewer_for_approved_status(tmp_path: Path) -> None:
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-002",
                    "action": "replace",
                    "entity_type": "building",
                    "entity_id": "cubo-20",
                    "field": "description",
                    "reason": "Trim portal payload",
                    "author": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "approved",
                }
            ],
        },
    )

    with pytest.raises(ManualCorrectionsError) as exc:
        load_manual_corrections(registry_path)

    assert "reviewer is required" in str(exc.value)


def test_load_manual_corrections_rejects_missing_exact_target_selector(tmp_path: Path) -> None:
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-003",
                    "action": "set_null",
                    "entity_type": "place",
                    "field": "description",
                    "reason": "Invalid target selector",
                    "author": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "draft",
                }
            ],
        },
    )

    with pytest.raises(ManualCorrectionsError) as exc:
        load_manual_corrections(registry_path)

    assert "entity_id must be a non-empty string" in str(exc.value)


def test_load_manual_corrections_rejects_ambiguous_priority_conflicts(tmp_path: Path) -> None:
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-004a",
                    "action": "set_null",
                    "entity_type": "place",
                    "entity_id": "office-ufficio-cubo-4c-piano-3",
                    "field": "meeting_url",
                    "reason": "Test conflict A",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "approved",
                    "priority": 10,
                },
                {
                    "id": "rule-004b",
                    "action": "replace",
                    "entity_type": "place",
                    "entity_id": "office-ufficio-cubo-4c-piano-3",
                    "field": "meeting_url",
                    "reason": "Test conflict B",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:01:00+00:00",
                    "status": "approved",
                    "priority": 10,
                },
            ],
        },
    )

    with pytest.raises(ManualCorrectionsError) as exc:
        load_manual_corrections(registry_path)

    assert "ambiguous priority conflict" in str(exc.value)


def test_select_rule_for_target_picks_highest_priority_applyable_rule(tmp_path: Path) -> None:
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-005-draft",
                    "action": "replace",
                    "entity_type": "building",
                    "entity_id": "cubo-20",
                    "field": "description",
                    "reason": "Draft should not be applyable",
                    "author": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "draft",
                    "priority": 50,
                },
                {
                    "id": "rule-005-approved-low",
                    "action": "replace",
                    "entity_type": "building",
                    "entity_id": "cubo-20",
                    "field": "description",
                    "reason": "Lower priority approved rule",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:01:00+00:00",
                    "status": "approved",
                    "priority": 5,
                },
                {
                    "id": "rule-005-applied-high",
                    "action": "replace",
                    "entity_type": "building",
                    "entity_id": "cubo-20",
                    "field": "description",
                    "reason": "Higher priority applyable rule",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:02:00+00:00",
                    "status": "applied",
                    "priority": 10,
                },
            ],
        },
    )

    rules = load_manual_corrections(registry_path)
    selected = select_rule_for_target(
        rules,
        CorrectionTarget(
            entity_type="building",
            entity_id="cubo-20",
            field="description",
        ),
    )

    assert selected is not None
    assert selected.id == "rule-005-applied-high"


def test_load_destructive_allowlist_supports_empty_registry(tmp_path: Path) -> None:
    allowlist_path = tmp_path / "destructive_allowlist.yaml"
    _write_payload(allowlist_path, {"version": 1, "allowed_rule_ids": []})

    loaded = load_destructive_allowlist(allowlist_path)

    assert loaded.version == 1
    assert loaded.allowed_rule_ids == frozenset()

