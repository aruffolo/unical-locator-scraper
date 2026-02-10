# UnicalLocator Scraper Execution Status

Last updated: 2026-02-10
Owner: Elrond89

## Legend
- `todo`: not started
- `in_progress`: active work
- `done`: completed and verified
- `blocked`: cannot proceed safely without input/dependency

## Current Baseline (2026-02-10)
- Tests: `51 passed`
- Validation: all datasets schema-valid
- Integrity: no issues
- Dataset baseline:
  - `buildings.json`: 150 records
  - `places.json`: 522 records of type `AULA` (549 total places)
  - `aulas.json`: 522 records
  - `departments.json`: 14 records
  - `people.json`: 4140 records
  - `aliases.json`: 1360 records
- Aula linkage quality:
  - `aulas` with `building_id`: 522/522 (`100%`)
  - `aulas` with `floor`: 208/522
  - `aulas` with `capacity`: 273/522

## Workstream Status

| Workstream | Status | Owner | Notes |
|---|---|---|---|
| Source inventory (`sources.json`) | in_progress | Elrond89 | Extended source set (department `strutture`, planner public API, CLA autonomy page) |
| Departments extraction | done | Elrond89 | Extracted and normalized |
| Buildings extraction (cubi + others) | done | Elrond89 | Campus map extraction complete |
| Services/places extraction | done | Elrond89 | Services + museum split implemented |
| Aule extraction/search (variable naming use case) | done | Elrond89 | Multi-source pass active (map KML + department tables + planner public API incl. `Impegni/getImpegniPublic` + CLA autonomy source), `aulas.json` + AULA entries in `places.json` |
| Coordinates completion | done | Elrond89 | Building coordinates currently complete |
| Coverage/integrity expansion | done | Elrond89 | Report includes `buildings`/`places`/`aulas` metrics and integrity checks |

## Technical Debt / Issues
- `Aule/getPerAutoCompletePublic` remains capped at 100; extraction now combines wider `Impegni/getImpegniPublic` window and curated public `linkCalendarioId` seeds, but both are still indirectly bounded by planner public API behavior.
- Curated planner `linkCalendarioId` list requires periodic refresh because departments can rotate links over time.
- Cross-source aula dedupe intentionally keeps one canonical record (`normalized_name` + `building_id`), but provenance (`source_url`) may reflect one source when multiple sources report the same aula.
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
- 2026-02-10: Expanded default department `strutture` source set to all 14 UNICAL department domains (+ legacy `www2.dimes`) and added floor/capienza extraction from table variants.
- 2026-02-10: Added `capacity` field to `aulas.json` schema and report coverage metrics (`with_capacity`).
- 2026-02-10: Added dedicated accordion parsing for `strutture` pages (CTC pattern), extracting `Aula CH-*`, `Laboratorio ...`, and `Aula Studio` with floor/capacity/building hints.
- 2026-02-10: Added Polifunzionale/capannoni mapping pass and source-specific building overrides.
- 2026-02-10: Resolved remaining missing aula links with manual-source rules and dropped confirmed false-positive planner entries.
- 2026-02-10: Added CLA `studio-in-autonomia` extraction for multimedia labs and mapped them to CLA building context.

## Blockers
- No hard blockers at this checkpoint.

## Next Checkpoint Template
- Date:
- Completed since last update:
- New blockers:
- Debt added/removed:
- Plan adaptations:
- Gate results (`pytest`, `validate`, `report`):
