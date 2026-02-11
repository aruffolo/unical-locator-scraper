# Scraping Phase Plan Progress

## Status Legend
- TODO
- IN_PROGRESS
- DONE
- BLOCKED

## Current Snapshot
- Date: 2026-02-11
- Overall status: IN_PROGRESS
- Canonical plan: `SCRAPING_PHASE_PLAN_UNICAL.md` (this folder)
- Canonical datasets path: `scraper/data/normalized`
- Next milestone: close Phase 1 hardening gaps, then complete Phase 4 operational hardening

## Verification Snapshot (2026-02-11)
- `pytest -q`: 69 passed
- `python -m unical_scraper validate --data-dir data/normalized --schemas-dir data/schema`: OK + integrity OK
- `python -m unical_scraper report --data-dir data/normalized --schemas-dir data/schema --out data/normalized/report.json`: generated

## Phase Checklist

### Phase 0 — Foundations and standards
- [x] DONE Package structure established (`extract`, `transform`, `validate`, `utils`)
- [x] DONE Deterministic JSON writing and sorted outputs
- [x] DONE Validation/report CLI contracts in place
- [x] DONE Schema + normalized dataset alignment present

### Phase 1 — Teachers pipeline (MVP vertical slice)
- [x] DONE Teachers crawl command writes `people.json` and updates `sources.json`
- [x] DONE API-driven teachers extraction path implemented with deterministic ordering
- [x] DONE Tests exist for teachers API extraction path
- [x] DONE Source-specific selector hardening for current known teacher page layouts
- [ ] IN_PROGRESS Rich office extraction still missing (`office_hours`, `office_place_id` currently 0 in report)

### Phase 2 — Departments and services expansion
- [x] DONE `crawl departments` implemented and normalized output produced
- [x] DONE `crawl services` implemented and normalized output produced
- [x] DONE Integrity checks include `people.department_id` references
- [ ] IN_PROGRESS `people.department_id` coverage remains partial (1332/4140, ~32.17%)

### Phase 3 — Places/buildings enrichment and linking
- [x] DONE Buildings extraction and normalization in place (`buildings.json`)
- [x] DONE Place-to-building linking flow implemented (`link places-buildings`)
- [x] DONE Alias generation flow implemented (`link aliases`)
- [x] DONE Optional coordinates included where available (buildings complete; places partial)

### Phase 3.1 — Aulas schema and linking
- [x] DONE `aulas.schema.json` + `aulas.json` present
- [x] DONE Deterministic `aulas.place_id -> places.place_id` linking
- [x] DONE Aulas include search fields (`name`, `normalized_name`, optional `short_code`)
- [x] DONE Building/floor/room/capacity fields carried when available

### Phase 4 — Quality hardening and release workflow
- [x] DONE Contributor gate commands and CI checks exist
- [x] DONE Coverage/report + contract consistency guardrails exist in CI
- [ ] IN_PROGRESS Retry/backoff and scrape diagnostics are limited
- [ ] IN_PROGRESS Teacher parser robustness for source HTML variations remains open

## Data & Coverage Snapshot (`data/normalized/report.json`)
- people total: 4140
- people with email: 1376 (33.24%)
- people with department_id: 1332 (32.17%)
- people with office_hours: 0
- people with office_place_id: 0
- places total: 544 (AULA: 517)
- places with building_id: 539 (99.08%)
- aulas total: 517
- aulas with building_id: 517 (100%)
- aulas with floor: 329 (63.64%)
- aulas with capacity: 280 (54.16%)

## Open Work (Priority)
1. Improve people enrichment (department mapping quality, office fields where public data is available).
2. Add explicit retry/backoff + structured scrape diagnostics for fragile endpoints.
3. Expand teacher parser fixtures for additional HTML variants as they are discovered.
4. Keep release gates green after each extraction/normalization refresh.

## Notes
- Duplicate parent data root (`../data`) was removed; scraper-local `data/` is now the only source of truth.
- Backend already defaults to `../scraper/data/normalized` and remains aligned with this source.
