from __future__ import annotations

from unical_scraper.validate.coverage_gate import check_coverage_guardrails


def _report(total: int, with_floor: int, with_building_id: int) -> dict[str, object]:
    return {
        "coverage": {
            "aulas": {
                "total": total,
                "with_floor": with_floor,
                "with_building_id": with_building_id,
            }
        }
    }


def test_coverage_guardrails_pass_on_non_decreasing_floor_and_full_building_linkage() -> None:
    baseline = _report(total=100, with_floor=60, with_building_id=100)
    candidate = _report(total=100, with_floor=63, with_building_id=100)

    violations = check_coverage_guardrails(
        baseline_report=baseline,
        candidate_report=candidate,
    )
    assert violations == []


def test_coverage_guardrails_fail_when_floor_coverage_decreases() -> None:
    baseline = _report(total=100, with_floor=60, with_building_id=100)
    candidate = _report(total=100, with_floor=59, with_building_id=100)

    violations = check_coverage_guardrails(
        baseline_report=baseline,
        candidate_report=candidate,
    )
    assert any("with_floor decreased" in item for item in violations)


def test_coverage_guardrails_fail_when_building_linkage_is_not_total() -> None:
    baseline = _report(total=100, with_floor=60, with_building_id=100)
    candidate = _report(total=100, with_floor=60, with_building_id=99)

    violations = check_coverage_guardrails(
        baseline_report=baseline,
        candidate_report=candidate,
    )
    assert any("with_building_id must equal total" in item for item in violations)
