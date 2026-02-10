# UnicalLocator Scraper Execution Status

Last updated: 2026-02-09
Owner: Elrond89

## Legend
- `todo`: not started
- `in_progress`: active work
- `done`: completed and verified
- `blocked`: cannot proceed safely without input/dependency

## Current Baseline (2026-02-09)
- Tests: `39 passed`
- Validation: all datasets schema-valid
- Integrity: no issues
- Dataset baseline:
  - `buildings.json`: 137 records
  - `places.json`: 335 records of type `AULA` (362 total places)
  - `aulas.json`: 335 records
  - `departments.json`: 14 records
  - `people.json`: 4140 records

## Workstream Status

| Workstream | Status | Owner | Notes |
|---|---|---|---|
| Source inventory (`sources.json`) | in_progress | Elrond89 | 5 official sources tracked, including aula map extraction |
| Departments extraction | done | Elrond89 | Extracted and normalized |
| Buildings extraction (cubi + others) | done | Elrond89 | Campus map extraction complete |
| Services/places extraction | done | Elrond89 | Services + museum split implemented |
| Aule extraction/search (variable naming use case) | done | Elrond89 | Multi-source pass active (map KML + department tables + planner public API incl. `Impegni/getImpegniPublic`), `aulas.json` + AULA entries in `places.json` |
| Coordinates completion | done | Elrond89 | Building coordinates currently complete |
| Coverage/integrity expansion | done | Elrond89 | Report includes `buildings`/`places`/`aulas` metrics and integrity checks |

## Technical Debt / Issues
- `Aule/getPerAutoCompletePublic` remains capped at 100; extraction now combines wider `Impegni/getImpegniPublic` window and curated public `linkCalendarioId` seeds, but both are still indirectly bounded by planner public API behavior.
- Curated planner `linkCalendarioId` list requires periodic refresh because departments can rotate links over time.
- Some service entities remain intentionally non-linkable (`building_id = null`) because they are virtual or multi-site.
- Aula aliases are now generated deterministically, but ranking/consumption policy must still be defined in the future app search layer.

## Adaptations / Decisions Log
- 2026-02-09: Keep execution in phased slices (source inventory -> departments -> buildings -> places -> coordinates -> quality hardening).
- 2026-02-09: Use official UNICAL sources first; external map sources only for unresolved coordinates, with explicit provenance.
- 2026-02-09: Preserve deterministic IDs/order as non-negotiable release constraint.
- 2026-02-09: Add explicit `AULA` workstream for variable-name lookup with building + level context.
- 2026-02-09: Implemented `crawl aulas` from official UNICAL map KML + floor-level aula parsing from placemark descriptions.
- 2026-02-09: Expanded `crawl aulas` to include department structure tables and planner public API enrichment.
- 2026-02-09: Added planner public impegni pass to bypass 100-result aula autocomplete cap.
- 2026-02-09: Expanded planner impegni window (`2020-2030`, limit `20000`) and seeded extraction with curated public `linkCalendarioId` set from department web pass.
- 2026-02-09: Relaxed planner aula label acceptance (with explicit sports/noise filters) to keep non-standard but valid classroom labels.
- 2026-02-10: Added `link aliases` pipeline to generate deterministic `aliases.json` for AULA/PLACE variant recall, with integrity checks on alias targets.

## Blockers
- No hard blockers at this checkpoint.

## Next Checkpoint Template
- Date:
- Completed since last update:
- New blockers:
- Debt added/removed:
- Plan adaptations:
- Gate results (`pytest`, `validate`, `report`):
