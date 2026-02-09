# unical-scraper

Starter ETL package for collecting and validating public UNICAL dataset files.

## Data Layout

- Schemas: `data/schema/`
- Normalized datasets: `data/normalized/`
- Aula contract:
  - `data/schema/aulas.schema.json`
  - `data/normalized/aulas.json`
  - linked by `place_id` to `places.json` entries of type `AULA`

## Quality Gates

Run from `scraper/`:

```bash
.venv/bin/pytest -q
.venv/bin/python -m unical_scraper validate --data-dir data/normalized --schemas-dir data/schema
.venv/bin/python -m unical_scraper report --data-dir data/normalized --schemas-dir data/schema --out data/normalized/report.json
```

## Aula Extraction

Run:

```bash
.venv/bin/python -m unical_scraper crawl aulas
```

This command updates both:
- `data/normalized/aulas.json`
- `data/normalized/places.json` (upserts `type: "AULA"` records)
