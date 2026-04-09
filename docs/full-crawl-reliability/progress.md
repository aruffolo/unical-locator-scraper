# Full Crawl Reliability Progress

## Rule

Only one phase may be active at a time.

A phase can be marked complete only after:
- code landed
- phase-specific verification passed
- any new blocker recorded below

## Phase Checklist

- [x] Phase 1. Services hard-failure fix
- [x] Phase 2. Aulas observability
- [x] Phase 3. Aulas control knobs
- [x] Phase 4. Planner request caching
- [x] Phase 5. Full replay wrapper

## Current Status

- Active phase: complete
- Next phase after verification: first real operator use on reported bad data

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
- Phase 2:
  - `.venv/bin/pytest -q tests/test_extract_aulas.py` -> `12 passed`
  - live `/tmp` smoke run:
    - `.venv/bin/python -m unical_scraper crawl aulas --base-url https://www.unical.it/campus/visita-il-campus/mappa/ --aulas-file /tmp/unical-aulas-progress-*/aulas.json --places-file /tmp/unical-aulas-progress-*/places.json --buildings-file /tmp/unical-aulas-progress-*/buildings.json --cache-dir .cache`
    - observed live progress output before completion:
      - `map: extracted 6 raw aulas`
      - `departments: extracted 378 raw aulas from 16 pages`
      - `planner: loaded 90 buildings and 100 aula summaries`
      - `planner details: processed 25/100 ... 100/100`
      - `planner discovery: scanned 20/84 ... 84/84`
      - `planner public links: querying 151 calendar ids`
- Phase 3:
  - `.venv/bin/pytest -q tests/test_extract_aulas.py tests/test_cli_aulas.py` -> `15 passed`
  - constrained `/tmp` smoke run:
    - `.venv/bin/python -m unical_scraper crawl aulas --base-url https://www.unical.it/campus/visita-il-campus/mappa/ --aulas-file /tmp/unical-aulas-constrained-*/aulas.json --places-file /tmp/unical-aulas-constrained-*/places.json --buildings-file /tmp/unical-aulas-constrained-*/buildings.json --cache-dir .cache --timeout 10 --no-planner-discovery --no-planner-public-links --no-planner-impegni`
    - result:
      - `planner public links: disabled`
      - `planner impegni: disabled`
      - `HTTP diagnostics` reported `0` requests and `0` final failures on cached replay
      - `Crawled raw aulas: 415`
      - `Normalized aulas: 400`
- Phase 4:
  - `.venv/bin/pytest -q tests/test_html_cache.py tests/test_extract_aulas.py` -> `17 passed`
  - two-pass `/tmp` replay against a fresh cache dir:
    - `.venv/bin/python -m unical_scraper crawl aulas --base-url https://www.unical.it/campus/visita-il-campus/mappa/ --aulas-file /tmp/unical-aulas-cache-run1-*/aulas.json --places-file /tmp/unical-aulas-cache-run1-*/places.json --buildings-file /tmp/unical-aulas-cache-run1-*/buildings.json --cache-dir /tmp/unical-aulas-cache-* --timeout 10 --no-planner-discovery --planner-max-link-ids 1 --no-planner-impegni`
    - same command repeated into `/tmp/unical-aulas-cache-run2-*` with the same `--cache-dir`
    - result:
      - pass 1: `HTTP diagnostics` reported `121` requests, `0` final failures
      - pass 2: `HTTP diagnostics` reported `0` requests, `0` final failures
      - both passes produced `Crawled raw aulas: 432`, `Normalized aulas: 413`
- Phase 5:
  - `.venv/bin/pytest -q tests/test_cli_full.py tests/test_cli_aulas.py` -> `3 passed`
  - real wrapper smoke run:
    - `.venv/bin/python -m unical_scraper crawl full --profile fast --data-dir /tmp/unical-full-fast-*/ --cache-dir .cache`
    - result:
      - departments/buildings/services completed
      - teachers explicitly skipped by `fast` profile
      - aulas completed with bounded planner path
      - `contract`, `validate`, `report` completed
      - wrapper ended with `[crawl full] complete`
- Final verification:
  - `.venv/bin/pytest -q` -> `120 passed`

## Blockers

- no active implementation blocker
- operational caveat:
  - `crawl full --profile fast` skips teacher crawling to stay reliable
  - `crawl full --profile full` keeps the broader network path, including teachers
