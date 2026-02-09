# unical-scraper

Starter ETL package for collecting and validating public UNICAL dataset files.

## Data Layout

- Schemas: `data/schema/`
- Normalized datasets: `data/normalized/`

## Quality Gates

Run from `scraper/`:

```bash
.venv/bin/pytest -q
.venv/bin/python -m unical_scraper validate --data-dir data/normalized --schemas-dir data/schema
.venv/bin/python -m unical_scraper report --data-dir data/normalized --schemas-dir data/schema --out data/normalized/report.json
```
