"""Coverage guardrails for CI report regression checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"report at '{path}' is not a JSON object")
    return payload


def _extract_aulas_coverage(report: dict[str, Any]) -> dict[str, Any]:
    coverage = report.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError("report missing 'coverage' object")

    aulas = coverage.get("aulas")
    if not isinstance(aulas, dict):
        raise ValueError("report missing 'coverage.aulas' object")

    return aulas


def check_coverage_guardrails(
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
) -> list[str]:
    """Return guardrail violations between baseline and candidate reports."""
    violations: list[str] = []

    baseline_aulas = _extract_aulas_coverage(baseline_report)
    candidate_aulas = _extract_aulas_coverage(candidate_report)

    baseline_with_floor = int(baseline_aulas.get("with_floor") or 0)
    candidate_with_floor = int(candidate_aulas.get("with_floor") or 0)
    if candidate_with_floor < baseline_with_floor:
        violations.append(
            "coverage regression: "
            f"coverage.aulas.with_floor decreased ({baseline_with_floor} -> {candidate_with_floor})"
        )

    candidate_total = int(candidate_aulas.get("total") or 0)
    candidate_with_building = int(candidate_aulas.get("with_building_id") or 0)
    if candidate_total > 0 and candidate_with_building != candidate_total:
        violations.append(
            "coverage regression: "
            "coverage.aulas.with_building_id must equal total "
            f"({candidate_with_building}/{candidate_total})"
        )

    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description="Check CI coverage guardrails.")
    parser.add_argument("--baseline", required=True, type=Path, help="Baseline report JSON path.")
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate report JSON path.")
    args = parser.parse_args()

    baseline_report = _read_report(args.baseline)
    candidate_report = _read_report(args.candidate)
    violations = check_coverage_guardrails(
        baseline_report=baseline_report,
        candidate_report=candidate_report,
    )

    if violations:
        for violation in violations:
            print(f"[FAIL] {violation}")
        raise SystemExit(1)

    print("[OK] coverage guardrails")


if __name__ == "__main__":
    main()
