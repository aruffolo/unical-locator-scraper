# UnicalLocator Scraper Execution Status

Last updated: 2026-02-10
Owner: Elrond89

## Legend
- `todo`: not started
- `in_progress`: active work
- `done`: completed and verified
- `blocked`: cannot proceed safely without input/dependency

## Current Baseline (2026-02-10)
- Tests: `56 passed`
- Validation: all datasets schema-valid
- Integrity: no issues
- Dataset baseline:
  - `buildings.json`: 151 records
  - `places.json`: 517 records of type `AULA` (544 total places)
  - `aulas.json`: 517 records
  - `departments.json`: 14 records
  - `people.json`: 4140 records
  - `aliases.json`: 1374 records
- Aula linkage quality:
  - `aulas` with `building_id`: 517/517 (`100%`)
  - `aulas` with `floor`: 329/517
  - `aulas` with `capacity`: 280/517

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
- Landmark alias mapping is currently config-driven (curated labels from campus map/PDF); it should be periodically reviewed when map labeling changes.
- Crawl command for full aulas refresh can intermittently stall on remote endpoints; current floor enrichment pass applied deterministically on normalized datasets with matching normalization rule in code.
- Remaining floor gaps are concentrated in records where source pages provide building but not explicit floor (notably CLA generic labels, Polifunzionale generic labels, and some legacy planner labels).
- Remaining floor gaps on phase-3 target buildings after this pass: `cla-centro-linguistico-d-ateneo` (10), `polifunzionale` (7), `polifunzionale-dfssn` (6), `cubo-15b` (8), `cubo-17b` (5), `cubo-29b` (0), `cubo-29c` (1).

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
- 2026-02-10: Final freeze pass executed (`pytest`, `validate`, `report`) with clean gates; dataset marked release-ready at this checkpoint.
- 2026-02-10: Added landmark/search alias pass (`link aliases`) for map/PDF labels (PTU, TAU, Rettorato, Biblioteche, CLA, Polo Infanzia, etc.) and added `cappella-universitaria` building landmark entity.
- 2026-02-10: Added deterministic capannone floor enrichment rule (`capannone-*` + missing floor -> `Piano Terra`) and propagated to normalized `aulas/places`.
- 2026-02-10: Added floor enrichment pass from explicit department-structure evidence (`dimes`/`dimeg`) and deterministic code hints (`CH-*`, `Lab *_nP`, `45B0*`, ponte markers), increasing floor coverage by +31.
- 2026-02-10: Fixed table-parser column alignment on empty `<td>` cells and extended capacity extraction (`54posti`/`60persone` forms), improving `capacity` coverage and reducing noisy duplicate aula variants.
- 2026-02-10: Extended floor extraction for department rows (`4º piano`, `ponte carrabile/pedonale`, `sottovia`) and added normalize hints (`29B1/29C2` code-floor inference, `superiore/inferiore`, planner/DIAM `Giannattasio`), increasing floor coverage by +73 (256 -> 329).

## Blockers
- No hard blockers at this checkpoint.

## Next Checkpoint Template
- Date:
- Completed since last update:
- New blockers:
- Debt added/removed:
- Plan adaptations:
- Gate results (`pytest`, `validate`, `report`):
