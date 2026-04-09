# Full Crawl Reliability Plan

## Goal

Make `/tmp` full crawler replays reliable enough for routine health checks without writing into canonical `data/normalized/`.

Current failure modes observed:
- `crawl services` aborts on junk archive/media links returning `403`.
- `crawl aulas` spends a long time in planner-heavy remote phases with no visible progress.
- planner POST-heavy phases are not cached, so reruns keep paying the same network cost.
- there is no single safe wrapper command for replaying the whole pipeline.

## Non-Goals

- No schema changes.
- No canonical dataset refresh in this work.
- No silent relaxation of validation/integrity rules.
- No broad source coverage expansion beyond making the current pipeline operational.

## Sequencing Rule

Work is strictly sequential.

Do not start phase `N+1` until phase `N` is:
- implemented
- covered by regression/smoke verification
- recorded in `progress.md` as complete

If a phase reveals new blockers, stop there and update the plan/progress before continuing.

## Phases

### Phase 1. Services hard-failure fix

Scope:
- filter non-service archive/media URLs from service link discovery/canonicalization
- remove false-positive `403` failures from strict `crawl services`

Deliverables:
- source filtering change in service extraction path
- regression test proving `/media/medias/...` links are excluded

Exit checks:
- targeted service tests pass
- strict `crawl services` smoke run in `/tmp` no longer fails on those known junk links

### Phase 2. Aulas observability

Scope:
- add explicit progress output for each major aulas phase
- add periodic progress counters in long planner loops

Deliverables:
- phase logs for map, department pages, planner summary list, public links, impegni
- incremental counters for long-running planner sections

Exit checks:
- targeted aulas tests pass
- manual `/tmp` smoke run shows visible progress during long planner work

### Phase 3. Aulas control knobs

Scope:
- add CLI controls to disable or constrain heavy planner paths

Expected knobs:
- `--planner-discovery/--no-planner-discovery`
- `--planner-public-links/--no-planner-public-links`
- `--planner-impegni/--no-planner-impegni`
- `--planner-max-link-ids`
- `--timeout`

Deliverables:
- CLI wiring
- extractor support with deterministic behavior when features are disabled/limited
- tests for flag behavior where practical

Exit checks:
- targeted CLI/aulas tests pass
- `/tmp` smoke run succeeds in a constrained mode suitable for health checks

### Phase 4. Planner request caching

Scope:
- extend cache beyond GET-only storage
- cache planner POST responses using deterministic request keys

Deliverables:
- request-aware cache support
- aulas planner path using cached POST responses
- regression tests for cache behavior

Exit checks:
- cache tests pass
- second constrained `/tmp` replay performs materially fewer live planner requests

### Phase 5. Full replay wrapper

Scope:
- add `crawl full` wrapper command for safe `/tmp` replays
- expose a stable replay mode intended for operators

Default direction:
- default profile should be `fast`
- `fast` favors reliability and observability over maximum remote coverage
- `full` keeps the broader planner coverage path available

Deliverables:
- `crawl full` command
- profile/default wiring
- README usage update

Exit checks:
- CLI tests pass
- `/tmp` smoke run via `crawl full --profile fast` completes end-to-end

## Verification Strategy

Per phase:
- add or update regression tests first when practical
- run only the targeted tests needed for the phase before advancing

Final verification after Phase 5:
- `.venv/bin/pytest -q`
- `.venv/bin/python -m unical_scraper validate --data-dir data/normalized --schemas-dir data/schema`
- `.venv/bin/python -m unical_scraper report --data-dir data/normalized --schemas-dir data/schema --out data/normalized/report.json`
- `/tmp` end-to-end replay through `crawl full --profile fast`

## Open Decisions Locked For Implementation

- `crawl full` default profile: `fast`
- `/tmp` replay is the operational target for this work, not canonical dataset refresh
- strict single-source commands remain available; reliability improvements should not hide real failures
