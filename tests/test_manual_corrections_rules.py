from __future__ import annotations

import json
from pathlib import Path

import pytest

from unical_scraper.transform.manual_corrections import (
    CorrectionTarget,
    ManualCorrectionsError,
    apply_manual_corrections_to_data_dir,
    load_destructive_allowlist,
    load_manual_corrections,
    select_rule_for_target,
)


def _write_payload(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_payload(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


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


def test_load_manual_corrections_normalizes_plural_entity_type_alias(tmp_path: Path) -> None:
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-001b",
                    "action": "replace",
                    "entity_type": "people",
                    "entity_id": "francesco-scarcello",
                    "field": "notes",
                    "value": "Updated notes",
                    "reason": "Alias acceptance test",
                    "author": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "draft",
                }
            ],
        },
    )

    rules = load_manual_corrections(registry_path)

    assert rules[0].target.entity_type == "person"


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


def test_apply_manual_corrections_blocks_destructive_rule_when_not_allowlisted(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "normalized"
    data_dir.mkdir(parents=True)
    places_path = data_dir / "places.json"
    _write_payload(
        places_path,
        [
            {
                "place_id": "service-centro-sportivo",
                "access_notes": "Obsolete text",
            }
        ],
    )
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-blocked-set-null",
                    "action": "set_null",
                    "entity_type": "place",
                    "entity_id": "service-centro-sportivo",
                    "field": "access_notes",
                    "reason": "Remove invalid notes",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "approved",
                }
            ],
        },
    )
    allowlist_path = tmp_path / "destructive_allowlist.yaml"
    _write_payload(allowlist_path, {"version": 1, "allowed_rule_ids": []})

    with pytest.raises(ManualCorrectionsError) as exc:
        apply_manual_corrections_to_data_dir(
            data_dir=data_dir,
            registry_path=registry_path,
            allowlist_path=allowlist_path,
            dataset_names=["places.json"],
        )

    assert "destructive rules must be allowlisted" in str(exc.value)
    assert "rule-blocked-set-null" in str(exc.value)


def test_apply_manual_corrections_updates_dataset_with_supported_actions(tmp_path: Path) -> None:
    data_dir = tmp_path / "normalized"
    data_dir.mkdir(parents=True)
    buildings_path = data_dir / "buildings.json"
    _write_payload(
        buildings_path,
        [
            {
                "building_id": "cubo-20",
                "description": "Old description",
                "nickname": "",
            },
            {
                "building_id": "cubo-21",
                "description": "Building on official UNICAL campus map - Cube 21",
                "nickname": "Keep me",
            },
        ],
    )
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-replace-desc",
                    "action": "replace",
                    "entity_type": "building",
                    "entity_id": "cubo-20",
                    "field": "description",
                    "value": "Dipartimento di Lingue e Scienze dell'Educazione",
                    "reason": "Canonical description",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "approved",
                    "priority": 10,
                },
                {
                    "id": "rule-override-empty-nickname",
                    "action": "override",
                    "entity_type": "building",
                    "entity_id": "cubo-20",
                    "field": "nickname",
                    "value": "Cubo Venti",
                    "reason": "Fill empty nickname",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:01:00+00:00",
                    "status": "approved",
                },
                {
                    "id": "rule-override-non-empty-noop",
                    "action": "override",
                    "entity_type": "building",
                    "entity_id": "cubo-21",
                    "field": "nickname",
                    "value": "Should not override",
                    "reason": "Do not replace existing nickname",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:02:00+00:00",
                    "status": "approved",
                },
                {
                    "id": "rule-drop-prefix",
                    "action": "drop_if_prefix",
                    "entity_type": "building",
                    "entity_id": "cubo-21",
                    "field": "description",
                    "patterns": ["Building on official UNICAL campus map"],
                    "reason": "Drop map boilerplate",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:03:00+00:00",
                    "status": "approved",
                },
            ],
        },
    )
    allowlist_path = tmp_path / "destructive_allowlist.yaml"
    _write_payload(
        allowlist_path,
        {"version": 1, "allowed_rule_ids": ["rule-drop-prefix"]},
    )

    summary = apply_manual_corrections_to_data_dir(
        data_dir=data_dir,
        registry_path=registry_path,
        allowlist_path=allowlist_path,
        dataset_names=["buildings.json"],
    )
    changed_rows = _read_payload(buildings_path)

    assert summary.datasets_scanned == ("buildings.json",)
    assert summary.rules_considered == 4
    assert summary.rules_applied == 3
    assert summary.fields_changed == 3
    assert isinstance(changed_rows, list)
    assert changed_rows[0]["description"] == "Dipartimento di Lingue e Scienze dell'Educazione"
    assert changed_rows[0]["nickname"] == "Cubo Venti"
    assert changed_rows[1]["description"] is None
    assert changed_rows[1]["nickname"] == "Keep me"


def test_apply_manual_corrections_rejects_unsupported_apply_time_action(tmp_path: Path) -> None:
    data_dir = tmp_path / "normalized"
    data_dir.mkdir(parents=True)
    places_path = data_dir / "places.json"
    _write_payload(
        places_path,
        [
            {
                "place_id": "service-centro-sportivo",
                "name": "Centro Sportivo",
            }
        ],
    )
    registry_path = tmp_path / "manual_corrections.yaml"
    _write_payload(
        registry_path,
        {
            "version": 1,
            "corrections": [
                {
                    "id": "rule-unsupported-alias",
                    "action": "alias",
                    "entity_type": "place",
                    "entity_id": "service-centro-sportivo",
                    "field": "name",
                    "reason": "Not implemented in apply step yet",
                    "author": "Elrond89",
                    "reviewer": "Elrond89",
                    "created_at": "2026-04-07T10:00:00+00:00",
                    "status": "approved",
                }
            ],
        },
    )
    allowlist_path = tmp_path / "destructive_allowlist.yaml"
    _write_payload(allowlist_path, {"version": 1, "allowed_rule_ids": []})

    with pytest.raises(ManualCorrectionsError) as exc:
        apply_manual_corrections_to_data_dir(
            data_dir=data_dir,
            registry_path=registry_path,
            allowlist_path=allowlist_path,
            dataset_names=["places.json"],
        )

    assert "unsupported apply-time action 'alias'" in str(exc.value)
