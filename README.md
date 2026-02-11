# UNICAL Scraper

Deterministic data pipeline for UNICAL campus datasets.

## Scope

Main outputs in `data/normalized/`:
- `buildings.json`
- `places.json`
- `aulas.json`
- `people.json`
- `departments.json`
- `aliases.json`
- `sources.json`
- `report.json`
- `dataset_contract.json`

Schemas are in `data/schema/`.

## Commands

Run from `scraper/`:

```bash
.venv/bin/pytest -q
.venv/bin/python -m unical_scraper validate --data-dir data/normalized --schemas-dir data/schema
.venv/bin/python -m unical_scraper report --data-dir data/normalized --schemas-dir data/schema --out data/normalized/report.json
.venv/bin/python -m unical_scraper contract --data-dir data/normalized --out data/normalized/dataset_contract.json
```

Main extraction command:

```bash
.venv/bin/python -m unical_scraper crawl aulas --cache-dir .cache
```

## Release Guardrails

- Schema + integrity validation: `unical_scraper validate`
- Coverage guardrails in CI:
  - `coverage.aulas.with_floor` must not decrease vs baseline
  - `coverage.aulas.with_building_id == coverage.aulas.total`
- Contract sync guardrail in CI:
  - generated contract must match committed `data/normalized/dataset_contract.json`

## Dataset Contract

`data/normalized/dataset_contract.json` is app-facing metadata:
- `compatibility_version`: bump only for breaking client-contract changes
- `contract_version`: version of manifest format
- `revision`: deterministic hash over dataset hashes/counts
- per-dataset `records` and `sha256` for traceability

## Final Snapshot

- Aulas: `517`
- Aulas with `building_id`: `517/517` (`100%`)
- Aulas with `floor`: `329/517`
- Aulas with `capacity`: `280/517`

## What Did Not Go As Planned

- Public planner endpoint `Aule/getPerAutoCompletePublic` is capped at 100 rows.
  Workaround implemented: merge with `Impegni/getImpegniPublic` and curated public calendar links.
- Full crawl can intermittently stall on remote endpoints.
  Workaround implemented: cached runs (`--cache-dir .cache`) and deterministic normalization passes.
- Not all aula floors are published by official sources.
  Result: floor coverage is partial (`329/517`), especially for CLA/polifunzionale generic labels.
- Cross-source dedupe keeps one canonical record per identity key.
  Result: provenance may point to one source even when multiple sources reported the same aula.
