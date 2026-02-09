# UnicalLocator Scraper Execution Plan

Last updated: 2026-02-09
Owner: Elrond89

## Objectives
- Build deterministic, schema-valid UNICAL datasets from public sources.
- Maximize coverage for departments, buildings (cubi and other campus buildings), places, and people.
- Preserve provenance (`source_id`, `source_url`, timestamps) for each generated record.

## Scope and Constraints
- Public sources only (UNICAL websites first; external fallback only when needed).
- No live network calls in unit tests.
- Stable IDs and deterministic ordering required.
- Release gate: `unical_scraper validate` must pass.

## Execution Steps

### 1. Source Inventory and Prioritization
- Build a canonical source list in `data/normalized/sources.json` for:
  - teachers directory
  - departments pages
  - services/secretariats pages
  - buildings/cubi pages
- Assign source priority per entity (official UNICAL source first).
- Record crawl notes for traceability.

Deliverables:
- Expanded `sources.json`
- Source mapping note in PR description

### 2. Departments Pipeline (Complete)
- Implement extraction in `src/unical_scraper/extract/departments.py`.
- Normalize into `data/normalized/departments.json` with:
  - `department_id`, `name`
  - optional contacts and `website_url`
  - provenance fields
- Add deterministic parser fixtures and tests.

Deliverables:
- Working `crawl departments` command
- Updated tests

### 3. Buildings Pipeline (Cubi + Other Buildings)
- Add extraction module for buildings/cubi pages.
- Populate `data/normalized/buildings.json` with deterministic IDs.
- Add optional coordinates from official sources when available.

Deliverables:
- New/updated extraction + normalization logic
- Populated `buildings.json`

### 4. Places Pipeline and Linking
- Implement services/secretariats/place extraction in `src/unical_scraper/extract/services.py`.
- Populate `data/normalized/places.json` (`SERVICE`, `SECRETARY`, `OFFICE`, etc.).
- Link `building_id` and `department_id` where resolvable.

Deliverables:
- Working `crawl services` command
- Populated `places.json`

### 5. Coordinates Completion Pass
- Fill missing building coordinates with this policy:
  1) official UNICAL sources
  2) external geocoding fallback (e.g., Google Maps), explicitly flagged in provenance
- Keep deterministic numeric formatting.

Deliverables:
- Improved coordinate coverage in `buildings.json`/`places.json`
- Source traceability for each coordinate origin

### 6. Quality and Gap Closure
- Extend report metrics for non-people datasets:
  - buildings with coordinates
  - places with `building_id`
  - departments with website/email
- Add/extend integrity checks for:
  - invalid `primary_building_id`
  - invalid `building_id` on places

Deliverables:
- Enhanced `report.json`
- Integrity improvements

## Quality Gates per Logical Slice
Run from `scraper/`:
- `.venv/bin/pytest -q`
- `.venv/bin/python -m unical_scraper validate --data-dir ../data/normalized --schemas-dir ../data/schema`
- `.venv/bin/python -m unical_scraper report --data-dir ../data/normalized --schemas-dir ../data/schema --out ../data/normalized/report.json`

## Commit Strategy
- One logical change per commit.
- Conventional Commits format.
- Stage only touched files for each logical slice.
