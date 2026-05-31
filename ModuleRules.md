# Module rules

- `src/unical_scraper` owns scraper CLI, extraction, normalization, validation, and reporting code.
- `data/schema` owns JSON schema contracts for normalized outputs.
- `data/normalized` is canonical checked-in dataset output; update intentionally and review diffs.
- `data/corrections` and `data/supplements` contain manual deterministic inputs; do not hide corrections in scraper code.
- `tests` owns fixtures and validation coverage only; production code must not depend on test helpers.
- Network crawling should remain reproducible through documented cache/profile options.
- Keep generated cache/temp output out of commits unless explicitly part of canonical data.
