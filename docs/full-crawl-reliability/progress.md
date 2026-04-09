# Full Crawl Reliability Progress

## Rule

Only one phase may be active at a time.

A phase can be marked complete only after:
- code landed
- phase-specific verification passed
- any new blocker recorded below

## Phase Checklist

- [x] Phase 1. Services hard-failure fix
- [ ] Phase 2. Aulas observability
- [ ] Phase 3. Aulas control knobs
- [ ] Phase 4. Planner request caching
- [ ] Phase 5. Full replay wrapper

## Current Status

- Active phase: Phase 2. Aulas observability
- Next phase after verification: Phase 3. Aulas control knobs

## Baseline Findings

- strict `/tmp` full replay failed in `crawl services` due to `403` archive/media URLs
- budgeted `/tmp` replay advanced through services and teachers, then spent multiple minutes in `crawl aulas`
- current aulas planner breadth:
  - `84` discovery URLs
  - `151` curated public link IDs
  - `Impegni` limit `20000`
- current cache stores GET responses only

## Verification Log

- Phase 1:
  - `.venv/bin/pytest -q tests/test_extract_services.py` -> `8 passed`
  - strict smoke run:
    - `.venv/bin/python -m unical_scraper crawl services --base-url https://www.unical.it/campus/servizi/ --out-file /tmp/unical-services-strict-*/places.json --cache-dir .cache`
    - result: `HTTP diagnostics` reported `0` requests and `0` final failures on cached replay
    - result: `Crawled 30 services`

## Blockers

- none currently beyond the known reliability defects above
