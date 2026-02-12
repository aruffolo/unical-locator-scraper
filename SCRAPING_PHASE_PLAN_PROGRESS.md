# Scraping Phase Plan Progress

## Status Legend
- TODO
- IN_PROGRESS
- DONE
- BLOCKED

## Current Snapshot
- Date: 2026-02-12
- Overall status: DONE
- Canonical plan: `SCRAPING_PHASE_PLAN_UNICAL.md` (this folder)
- Canonical datasets path: `scraper/data/normalized`
- Next milestone: maintenance mode (periodic refresh + gate checks)

## Verification Snapshot (2026-02-12)
- `pytest -q`: 90 passed
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
- [x] DONE Teacher detail API enrichment wired (`department_name`, `office_hours`, `office_reference`, `phone`)
- [x] DONE Teacher office places upsert flow wired in `crawl teachers` (`places.json` + `office_place_id` linking rules)
- [x] DONE Dataset refresh executed; people/office coverage materially improved

### Phase 2 — Departments and services expansion
- [x] DONE `crawl departments` implemented and normalized output produced
- [x] DONE `crawl services` implemented and normalized output produced
- [x] DONE Integrity checks include `people.department_id` references
- [x] DONE `people.department_id` coverage baseline accepted for current deterministic sources (1721/4156, ~41.41%)

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
- [x] DONE Retry/backoff and structured HTTP diagnostics available in crawl flows
- [x] DONE Teacher parser robustness hardened for known source HTML/API variations

## Data & Coverage Snapshot (`data/normalized/report.json`)
- people total: 4156
- people with email: 1469 (35.35%)
- people with department_id: 1721 (41.41%)
- people with office_hours: 438 (10.54%)
- people with office_place_id: 626 (15.06%)
- places total: 876 (AULA: 517, OFFICE: 333, SERVICE: 26)
- places with building_id: 871 (99.43%)
- aulas total: 517
- aulas with building_id: 517 (100%)
- aulas with floor: 329 (63.64%)
- aulas with capacity: 280 (54.16%)

## Open Work (Priority)
1. Keep release gates green after each extraction/normalization refresh.
2. Revisit `people.department_id` only if new deterministic sources become available.

## Notes
- Duplicate parent data root (`../data`) was removed; scraper-local `data/` is now the only source of truth.
- Backend already defaults to `../scraper/data/normalized` and remains aligned with this source.
