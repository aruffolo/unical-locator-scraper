# UnicalLocator Scraper Execution Status

Last updated: 2026-02-09
Owner: Elrond89

## Legend
- `todo`: not started
- `in_progress`: active work
- `done`: completed and verified
- `blocked`: cannot proceed safely without input/dependency

## Current Baseline (2026-02-09)
- Tests: `38 passed`
- Validation: all datasets schema-valid
- Integrity: no issues
- Dataset baseline:
  - `buildings.json`: 137 records
  - `places.json`: 31 records
  - `aulas.json`: 4 records
  - `departments.json`: 14 records
  - `people.json`: 4140 records

## Workstream Status

| Workstream | Status | Owner | Notes |
|---|---|---|---|
| Source inventory (`sources.json`) | in_progress | Elrond89 | 5 official sources tracked, including aula map extraction |
| Departments extraction | done | Elrond89 | Extracted and normalized |
| Buildings extraction (cubi + others) | done | Elrond89 | Campus map extraction complete |
| Services/places extraction | done | Elrond89 | Services + museum split implemented |
| Aule extraction/search (variable naming use case) | done | Elrond89 | `crawl aulas` implemented; `aulas.json` + AULA entries in `places.json` |
| Coordinates completion | done | Elrond89 | Building coordinates currently complete |
| Coverage/integrity expansion | done | Elrond89 | Report includes `buildings`/`places`/`aulas` metrics and integrity checks |

## Technical Debt / Issues
- Aula coverage is still partial (currently map-driven; no timetable/department-specific room registries ingested yet).
- Some service entities remain intentionally non-linkable (`building_id = null`) because they are virtual or multi-site.
- `search_tokens` for aulas are generated, but `aliases.json` is still empty and can be populated for stronger query recall.

## Adaptations / Decisions Log
- 2026-02-09: Keep execution in phased slices (source inventory -> departments -> buildings -> places -> coordinates -> quality hardening).
- 2026-02-09: Use official UNICAL sources first; external map sources only for unresolved coordinates, with explicit provenance.
- 2026-02-09: Preserve deterministic IDs/order as non-negotiable release constraint.
- 2026-02-09: Add explicit `AULA` workstream for variable-name lookup with building + level context.
- 2026-02-09: Implemented `crawl aulas` from official UNICAL map KML + floor-level aula parsing from placemark descriptions.

## Blockers
- No hard blockers at this checkpoint.

## Next Checkpoint Template
- Date:
- Completed since last update:
- New blockers:
- Debt added/removed:
- Plan adaptations:
- Gate results (`pytest`, `validate`, `report`):
