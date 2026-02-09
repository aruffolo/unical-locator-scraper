# UnicalLocator Scraper Execution Status

Last updated: 2026-02-09
Owner: Elrond89

## Legend
- `todo`: not started
- `in_progress`: active work
- `done`: completed and verified
- `blocked`: cannot proceed safely without input/dependency

## Current Baseline (2026-02-09)
- Tests: `7 passed`
- Validation: all datasets schema-valid
- Integrity: no issues
- Dataset baseline:
  - `buildings.json`: 0 records
  - `places.json`: 0 records
  - `departments.json`: 1 record
  - `people.json`: 1 record

## Workstream Status

| Workstream | Status | Owner | Notes |
|---|---|---|---|
| Source inventory (`sources.json`) | todo | Elrond89 | Need full official source list by entity |
| Departments extraction | todo | Elrond89 | Skeleton exists; parser implementation missing |
| Buildings extraction (cubi + others) | todo | Elrond89 | New extraction needed |
| Services/places extraction | todo | Elrond89 | Skeleton exists; parser implementation missing |
| Coordinates completion | todo | Elrond89 | Requires source-priority policy |
| Coverage/integrity expansion | todo | Elrond89 | Add metrics and link checks |

## Technical Debt / Issues
- `src/unical_scraper/extract/departments.py`: placeholder returns empty list.
- `src/unical_scraper/extract/services.py`: placeholder returns empty list.
- `src/unical_scraper/validate/report.py`: coverage only for `people.json`.
- `src/unical_scraper/validate/integrity.py`: does not yet validate building references.
- `sources.json`: currently only teachers source tracked.

## Adaptations / Decisions Log
- 2026-02-09: Keep execution in phased slices (source inventory -> departments -> buildings -> places -> coordinates -> quality hardening).
- 2026-02-09: Use official UNICAL sources first; external map sources only for unresolved coordinates, with explicit provenance.
- 2026-02-09: Preserve deterministic IDs/order as non-negotiable release constraint.

## Blockers
- Missing `ai-rules/rule-loading.md` and `ai-rules/project-structure.md` in current workspace; proceeding with `AGENTS.md` + parent project docs.

## Next Checkpoint Template
- Date:
- Completed since last update:
- New blockers:
- Debt added/removed:
- Plan adaptations:
- Gate results (`pytest`, `validate`, `report`):
