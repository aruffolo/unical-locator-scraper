---
summary: "Context budget for adding more agent rules, docs, and skills."
read_when:
  - Adding or expanding `AGENTS.md`, `ai-rules/`, `ai-docs/`, or skills.
  - Evaluating whether a proposed workflow should become a rule, doc, script, or skill.
  - Auditing context cost before adopting external agent discipline.
---
# Context Budget

Use this before adding more durable agent guidance.

## Current Budget Shape

- Always-loaded context should stay small: `AGENTS.md` plus `ai-rules/rule-loading.md`.
- Task rules should load only when the task needs them.
- `ai-docs/` should hold durable facts and audits, not task instructions that belong in rules.
- Skills should hold longer workflows, examples, and decision trees.

## Official Codex Limit

OpenAI's Codex docs say project instruction discovery stops when the combined `AGENTS.md` guidance reaches `project_doc_max_bytes`, which defaults to 32 KiB. This is a byte cap for discovered instruction files, not a recommended quality budget.

Official references:

- https://developers.openai.com/codex/guides/agents-md
- https://developers.openai.com/codex/config-advanced

Measure the current repo with the commands below. The route mechanism matters because loading all `ai-rules/` at once can exceed 32 KiB, while loading only relevant rules keeps normal work small.

## How To Test A Repo

Run these from the repo root.

Official discovery cap check:

```bash
wc -c ~/.codex/AGENTS.override.md ~/.codex/AGENTS.md AGENTS.override.md AGENTS.md 2>/dev/null
find . -path './.git' -prune -o \( -name 'AGENTS.md' -o -name 'AGENTS.override.md' \) -print
find . -path './.git' -prune -o \( -name 'AGENTS.md' -o -name 'AGENTS.override.md' \) -exec wc -c {} +
```

Interpretation:

- Root `AGENTS.md` should be far below 32 KiB.
- Nested `AGENTS.md` files count only when Codex starts inside that subtree.
- Generated folders such as `.venv`, `.pytest_cache`, `.cache`, or downloaded HTML caches can contain large generated files; do not start Codex inside them unless intentional.

Route-mechanism dry run:

```bash
wc -c AGENTS.md ai-rules/rule-loading.md ai-rules/project-structure.md
wc -c AGENTS.md ai-rules/rule-loading.md ai-rules/project-structure.md ai-docs/domain-language.md
wc -c AGENTS.md ai-rules/rule-loading.md ai-rules/project-structure.md ai-docs/context-budget.md
```

Worst-case anti-test:

```bash
wc -c AGENTS.md ai-rules/*.md ai-docs/*.md ModuleRules.md Package/ModuleRules.md 2>/dev/null
```

If the anti-test is above 32 KiB but routed task cases stay comfortably below it, the routing mechanism is working. If a normal task case approaches 32 KiB, move long examples or decision trees into skills or `ai-docs/` and keep `rule-loading.md` as the router only.

Skill dry run:

Skills are not part of the official `AGENTS.md` discovery cap. They are opt-in context paid only when the skill is invoked. Measure them as task context plus the selected skill, and include only extra files that the skill workflow would actually open.

```bash
test -d skills && wc -c skills/*/SKILL.md
```

For skills with referenced assets, scripts, templates, or examples, inspect references before counting everything:

```bash
rg -n "references/|assets/|templates/|scripts/|examples/" skills/<skill-name>/SKILL.md
wc -c skills/<skill-name>/SKILL.md skills/<skill-name>/<referenced-file>
```

Interpretation:

- Normal skill passes may exceed 32 KiB because that official cap is not the skill budget; still prefer compact context for quality.
- A skill `SKILL.md` above roughly 12 KiB deserves review before adding more text.
- If one skill routinely needs several large referenced files, split the workflow, move examples into lazily-read references, or convert mechanical steps into scripts.
- Do not add a new skill when an existing skill plus a short rule or script already covers the behavior.

## Add More When

- The guidance prevents repeated mistakes across repos.
- It changes agent behavior, not just human background knowledge.
- It can be routed by `rule-loading.md`, docs tooling, or skill trigger text.
- It has one clear owner location.

## Too Much Signals

- A proposal adds more than ~50 always-loaded words without removing something else.
- A rule file grows past ~700 words and contains multiple unrelated concerns.
- A doc must be read for most tasks but is not an actual rule.
- A skill duplicates an existing rule, Makefile target, or script.
- Agents need to read several docs before understanding a simple edit.

## Default Placement

- `AGENTS.md`: only session-critical protocol.
- `ai-rules/`: concise behavioral rules that should affect code decisions.
- `ai-docs/`: durable project facts, vocabulary, contracts, and audits.
- `scripts/`: executable checks or repeatable mechanical workflows.
- `skills/`: opt-in multi-step workflows with examples.

## Audit Method

Before adopting a new idea, measure:

- always-paid words: `AGENTS.md` plus always-loaded rules
- task-paid words: rules/docs/skills loaded for the likely task
- overlap: existing rule, script, Makefile, or skill that already covers it
- project fit: compare against Liquore, miniapphostsdkios, LastStand/flutter-app, and other relevant `Lavoro` repos

Prefer adding nothing when the idea is already covered by executable commands or existing rules.
