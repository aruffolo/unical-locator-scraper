# UnicalLocator Scraper Execution Status

Last updated: 2026-02-09
Owner: Elrond89

## Legend
- `todo`: not started
- `in_progress`: active work
- `done`: completed and verified
- `blocked`: cannot proceed safely without input/dependency

## Current Baseline (2026-02-09)
- Tests: `33 passed`
- Validation: all datasets schema-valid
- Integrity: no issues
- Dataset baseline:
  - `buildings.json`: 137 records
  - `places.json`: 27 records
  - `departments.json`: 14 records
  - `people.json`: 4140 records

## Workstream Status

| Workstream | Status | Owner | Notes |
|---|---|---|---|
| Source inventory (`sources.json`) | in_progress | Elrond89 | 4 official sources tracked; can expand with aula-specific sources |
| Departments extraction | done | Elrond89 | Extracted and normalized |
| Buildings extraction (cubi + others) | done | Elrond89 | Campus map extraction complete |
| Services/places extraction | done | Elrond89 | Services + museum split implemented |
| Aule extraction/search (variable naming use case) | todo | Elrond89 | New explicit workstream to implement |
| Coordinates completion | done | Elrond89 | Building coordinates currently complete |
| Coverage/integrity expansion | in_progress | Elrond89 | Report coverage still people-only |

## Technical Debt / Issues
- `src/unical_scraper/validate/report.py`: coverage still centered on `people`; needs `buildings`/`places`/`aule` metrics.
- `AULA` extraction path is missing (required for heterogeneous aula-name search use case).
- `places.json` intentionally keeps some multi-site/area services non-linkable (`building_id = null`).

## Adaptations / Decisions Log
- 2026-02-09: Keep execution in phased slices (source inventory -> departments -> buildings -> places -> coordinates -> quality hardening).
- 2026-02-09: Use official UNICAL sources first; external map sources only for unresolved coordinates, with explicit provenance.
- 2026-02-09: Preserve deterministic IDs/order as non-negotiable release constraint.
- 2026-02-09: Add explicit `AULA` workstream for variable-name lookup with building + level context.

## Blockers
- Missing `ai-rules/rule-loading.md` and `ai-rules/project-structure.md` in current workspace; proceeding with `AGENTS.md` + parent project docs.

## Next Checkpoint Template
- Date:
- Completed since last update:
- New blockers:
- Debt added/removed:
- Plan adaptations:
- Gate results (`pytest`, `validate`, `report`):
