UnicalLocator — Scraping Phase Plan
===================================

Purpose
-------
Define a clear execution plan for the data collection pipeline that produces deterministic,
versioned JSON datasets for UnicalLocator.

This plan covers extraction, normalization, validation, and reporting.
It does not cover mobile app features beyond data consumption.

Repository split
----------------
This plan assumes two separate repositories:
- `unical-locator-scraper`: scraping/ETL code, schemas, normalized datasets, validation/reporting.
- `unical-locator`: Flutter mobile app that consumes versioned dataset artifacts.

The current folder can remain a shared workspace for parallel development.

Source of truth
---------------
- `CODEX_PROJECT_BRIEF_UNICAL.md`
- `ER_SCHEMA_UNICAL_HUMAN.md`
- JSON Schemas in `data/schema/`

Guiding objectives
------------------
1) Build a reliable ETL pipeline for public UNICAL data only.
2) Keep output deterministic and PR-friendly (stable IDs, stable ordering, reproducible files).
3) Validate all generated datasets against JSON Schema and integrity rules.
4) Maximize data coverage for search-first use cases (people, places, departments, services).
5) Preserve provenance (`source_id`, `source_url`, timestamps) for traceability.
6) Keep architecture modular and testable with no backend dependency.

Constraints and non-goals
-------------------------
- No backend services in this phase.
- No indoor navigation concepts.
- No student personal/private data.
- Scrape only public UNICAL pages and respect responsible crawling (User-Agent, rate limits).
- Map remains secondary; building-level support only.

Phase overview
--------------
Phase 0: Foundations and standards
Phase 1: Teachers pipeline (MVP vertical slice)
Phase 2: Departments and services expansion
Phase 3: Places/buildings enrichment and linking
Phase 4: Quality hardening and release workflow

Detailed phases
---------------

Phase 0 — Foundations and standards
-----------------------------------
Goal:
- Freeze conventions before scale (IDs, folder layout, validation contract, CLI contract).

Scope:
- Confirm canonical entities and required fields for MVP from ER schema.
- Confirm file layout under `data/normalized/` and `data/schema/`.
- Define deterministic writing rules (sorting, formatting, timestamps policy).
- Define source registry conventions (`sources.json`).
- Keep scraper package structure stable (`extract`, `transform`, `validate`, `utils`).

Deliverables:
- Baseline scaffold under `scraper/`.
- Existing schemas aligned with normalized file names.
- Initial example records for key datasets.

Exit criteria:
- `unical_scraper validate` works on baseline datasets.
- Test suite passes for ID generation, normalization, and validation helpers.


Phase 1 — Teachers pipeline (MVP vertical slice)
------------------------------------------------
Goal:
- Deliver first production-ready ETL path for `people.json` from public teacher pages.

Scope:
- Crawl teacher listing/profile pages.
- Extract core fields: `full_name`, `email`, `website_url`, `source_url`, optional office info.
- Normalize into `PERSON` records with stable `person_id` and role `PROFESSOR`.
- Generate/update `sources.json` entry for teachers source.
- Add coverage metrics specific to people dataset.

Deliverables:
- `crawl teachers` command producing deterministic `data/normalized/people.json`.
- Unit tests for parser edge cases and normalization mappings.
- Validation and report support for teachers output.

Exit criteria:
- Re-running crawl on same input yields equivalent output.
- `people.json` passes schema validation.
- Integrity checks report no errors for produced references.


Phase 2 — Departments and services expansion
--------------------------------------------
Goal:
- Add organizational and service context needed for search and navigation.

Scope:
- Implement extraction for departments pages.
- Implement extraction for services/secretary offices pages.
- Normalize into `departments.json` and `places.json` (types: `SERVICE`, `SECRETARY`, etc.).
- Link people to departments where possible.

Deliverables:
- `crawl departments` and `crawl services` commands (MVP complete behavior).
- Deterministic output files for departments and places.
- Integrity rules for `department_id` references.

Exit criteria:
- `departments.json` and `places.json` validate against schemas.
- `people.department_id` references are mostly resolved and integrity-clean.


Phase 3 — Places/buildings enrichment and linking
-------------------------------------------------
Goal:
- Improve search quality and map readiness with linked place/building data.

Scope:
- Populate/normalize buildings dataset from available public sources.
- Map offices/services/classrooms to `building_id` and optional floor/room.
- Add alias records for robust search synonyms and abbreviations.
- Add optional coordinates where public data is available and reliable.

Deliverables:
- Enriched `buildings.json`, `places.json`, and optional `aliases.json` updates.
- Additional integrity checks for `building_id` and `office_place_id` relations.

Exit criteria:
- Building/place linking is coherent and validates.
- Coverage report shows measurable improvement for location-linked records.


Phase 4 — Quality hardening and release workflow
-------------------------------------------------
Goal:
- Make dataset refreshes predictable for contributors and CI.

Scope:
- Harden parser behavior for source HTML variations.
- Improve retry/error handling and scrape diagnostics.
- Add contributor workflow for crawl -> validate -> report.
- Define PR checklist and reproducibility checks.

Deliverables:
- Stable command sequence for refresh runs.
- Extended tests for regressions and integrity constraints.
- Documented contributor process for dataset updates.

Exit criteria:
- Dataset refresh can be run and reviewed in PRs with minimal manual cleanup.
- Validation/report outputs are consistently consumed as quality gates.

Milestones and decision gates
-----------------------------
M1 (end Phase 1):
- People pipeline is trusted and repeatable.

M2 (end Phase 2):
- Departments/services become first-class searchable data.

M3 (end Phase 3):
- Core cross-entity linking is in place for search + building-level map usage.

M4 (end Phase 4):
- Scraping workflow is contributor-ready and maintainable.

Quality KPIs (initial)
----------------------
- Schema pass rate: 100% for all normalized files.
- Integrity errors: 0 blocking errors.
- Determinism: no diff when rerunning unchanged sources.
- Coverage examples:
  - `% people with email`
  - `% people with department_id`
  - `% people with office_place_id`
  - `% places with building_id`

Operational workflow (target)
-----------------------------
1) Run crawl commands for target datasets.
2) Normalize/write deterministic JSON into `data/normalized/`.
3) Run `unical_scraper validate`.
4) Run `unical_scraper report`.
5) Open PR with dataset and report diffs.

Open decisions to resolve early
-------------------------------
- Canonical source list and priority order for each entity.
- Conflict policy when multiple sources disagree on a field.
- Timestamp policy (`last_verified_at` granularity and update conditions).
- Alias generation strategy (manual vs rule-based hybrid).

Immediate next execution slice
-----------------------------
- Complete Phase 1 parser selectors for real UNICAL teacher pages.
- Add fixture-based parser tests for known page layouts.
- Enforce deterministic ordering and strict validation in CI.

Phase 3.1 — Aulas schema and linking
------------------------------------
Goal:
- Add a classroom-specific dataset and linking contract for variable aula naming.

Scope:
- Introduce `aulas.json` + `aulas.schema.json`.
- Build deterministic linkage: `aulas.place_id -> places.place_id` (`PLACE.type = AULA`).
- Populate/search fields: `name`, `normalized_name`, optional `short_code`.
- Carry `building_id`, optional `floor` and `room` for user-facing location context.

Exit criteria:
- Aula dataset schema-valid and integrity-clean.
- Aula entries resolvable by code-like and full-name queries.
