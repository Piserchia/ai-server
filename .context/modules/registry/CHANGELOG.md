# Changelog: registry

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-09-10 — three atlas skill frontmatter tweaks (review-and-improve proposals from job ec792bc4)

**Agent task**: apply three `review-and-improve` proposals from the
idle-queue retrospective (2026-09-10, 30d window). All are small SKILL.md
frontmatter edits — no source code, no tests.

**Files changed**:
- `skills/atlas-value-monitor/SKILL.md` — raised `max_turns` 30 → 50 per
  proposal `a0792164-94bb-40ae-bfb7-744577f53026`. Rationale: 2 of 8 runs
  in the last 30 days (25%) hit `error_max_turns` at the current ceiling;
  the previous 20→30 bump on 2026-09-08 was re-hit the next day (job
  `b1f8cf18`, 2026-09-09 14:10). Successful runs complete in 60–150 s with
  fewer turns; busy days with expiries/assignments consume more. This
  raises the ceiling one more step without changing behavior.
- `skills/atlas-swing-trade/SKILL.md` — appended `.context/PROJECT_PROTOCOL.md`
  to `context_files` per proposal `bf94e0cb-0b77-44da-865d-b5cc533cbc2e`.
  Rationale: file was Read on 7 of 9 runs (78%). Preloading eliminates one
  Read tool call per run.
- `skills/atlas-trader-paper/SKILL.md` — appended `.context/PROJECT_PROTOCOL.md`
  to `context_files` per proposal `b5b252f7-9c15-439b-8ea4-5edeb2158141`.
  Rationale: file was Read on 6 of 11 runs (55%). Same pattern as
  atlas-swing-trade.

**Why**: closes the review-and-improve loop for three highest-signal
proposals from the retrospective. `context_files` preloads content the
session was already going to Read — same file, one turn earlier, no
behavior change. The `max_turns` bump is defense-in-depth against a
recurrent ceiling hit.

**Side effects**: none. `.context/PROJECT_PROTOCOL.md` exists at
`settings.server_root` (validator `registry/skills.py` and lint
`scripts/lint_docs.py:check_context_files_exist` both pass). The
`max_turns` raise is a ceiling change (no new authority, no new tools).

**Gotchas discovered**: none — this is the standard proposal-application
pattern established by the 2026-08-31 entry (atlas-report + ops-manager
context_files preload).

## 2026-09-08 — atlas-value-monitor: inline bootstrap + max_turns 20→30

**Files created**: none
**Files changed**:
- `skills/atlas-value-monitor/SKILL.md` — replaced step 1 body ("as in
  atlas-value-theses, incl. sitecustomize script") with the actual bootstrap
  commands inline (matches atlas-value-theses lines 26–28); raised
  `max_turns` from 20 → 30.

**Why**: audit `c2a04f63` (2026-09-08) burned all 20 turns hunting for the
bootstrap details across the workspace (tradingcore, tradier.py, weekly.py,
config, grep for "sitecustomize") and hit `error_max_turns` mid-hunt without
ever running pytest or `value.monitor`. Cross-skill reference is unfollowable
— `skills/` live outside the workspace clone, so the session literally can't
Read the file being cited. Inlining the commands removes the exploratory
work; the max_turns bump adds ~10 turns of headroom on top so the historically
tight-but-passing trajectory (bootstrap ~5 tool calls + pytest + monitor + env
poking = ~25 turns) has slack against the same recurrence.

**Side effects**: none. Skill body is self-contained now; the frontmatter
change is a ceiling raise (no new authority, no new tools). No runtime code
touched — the registry just re-parses the file on skill reload.

**Gotchas discovered**: same pattern as `_writeback` / `_learning_apply`
(TROUBLESHOOTING.md) — tight `max_turns` + a prompt that forces exploratory
work = intermittent `error_max_turns`. The fix is the prompt; the budget
bump is defense-in-depth. Cross-skill references ("do X like skill Y") are
particularly toxic: skills live outside the workspace clone so the session
can't actually resolve the reference.

## 2026-08-31 — atlas-report + ops-manager: pre-load `.context/SYSTEM.md` (review-and-improve proposals)

**Agent task**: implement two `review-and-improve` proposals adding
`context_files` to the highest-usage skill without any (atlas-report, 95
runs/30d) and to ops-manager (5/5 runs already re-Read SYSTEM.md).

**Files changed**:
- `skills/atlas-report/SKILL.md` — added `context_files: [".context/SYSTEM.md"]`
  (skill previously had none; 78%+ of runs Read SYSTEM.md per proposal
  `f6c24f53-4520-4dbb-95b4-c4a7c03a92c1`, subsumes older `fd162b91-4177-4f1f-a8b2-fae52d69bbd2`).
- `skills/ops-manager/SKILL.md` — appended `.context/SYSTEM.md` to the
  existing list (`CHARTER.md`, `MISSION.md`) per proposal
  `bfa0367e-6561-45ea-817f-3189236b84ae`.

**Why**: `context_files` are pre-loaded into the server directive so the
session skips a Read tool call it would otherwise make on nearly every
invocation. Zero behavior change — same file read, one turn earlier.

**Side effects**: none. The runtime validator (`registry/skills.py`) and
lint (`scripts/lint_docs.py check_context_files_exist`) both accept the
new paths — `.context/SYSTEM.md` is present in every checkout.

**Held back (recorded for follow-up)**: proposal `f6c24f53` also lists
`projects/atlas/dashboard/experts_charters/equity_analyst.md` and
`projects/atlas/dashboard/experts_knowledge/equity_analyst.md` (76% hit
rate each). Those files live in the atlas project (gitignored under
`projects/*/`), so they exist in production but NOT in server workspace
clones — declaring them would fail `check_context_files_exist` in the
workspace/dev repo even though the runtime would find them. That's a
separate fix (teach the lint to skip paths under gitignored project
subdirs) and is left as a follow-up.

**Gotchas discovered**: `check_context_files_exist` uses `REPO_ROOT / cf`
(the repo where lint runs); `test_context_files_exist` in
`tests/test_skill_contracts.py` uses `settings.server_root / cf` (the
production install path). For paths at `.context/`, `skills/`, `src/` they
agree; for paths under `projects/<slug>/` they diverge because projects
are gitignored — pull-only, deploy-time-hydrated clones.

## 2026-08-31 — skills loader fails closed on corrupt frontmatter (EVALUATION_2026-08-30 F1.6)

**Files changed**: `src/registry/skills.py`, `tests/test_registry_failclosed.py`.

- `_parse_frontmatter` raises `SkillFrontmatterError` on YAML errors or a
  non-mapping frontmatter block instead of returning `{}` (which made the
  skill run on registry defaults: full default toolset, acceptEdits,
  isolation none, default model). `load()` propagates it; `list_all()`
  logs ERROR and skips the corrupt skill so registry generation survives.
- Public interface change: callers of `load()` must expect
  `SkillFrontmatterError` (session maps it to a terminal job failure).

## 2026-08-10 — Delivery.env_files: gitignored secrets for workspace clones

**Files changed**: `src/registry/manifest.py`, `tests/test_manifest.py`.

**Why**: workspace clones don't carry gitignored files, so owner-provisioned
credentials (atlas's Alpaca keys in `.env`) never reached sessions. Projects
now declare `delivery.env_files: [".env"]` and the runner copies them in
(`runner/workspaces.provision_env_files` — see runner CHANGELOG same date).

**Schema**: `Delivery.env_files: list[str]`, default empty (fully
back-compat). `validate` rejects absolute/`~`-relative/`..`-traversing and
whitespace-wrapped entries so a manifest can never pull arbitrary host files
into a session-readable workspace.

**Verify**: `pipenv run pytest tests/test_manifest.py` (7 new tests).

## 2026-07-28 — Management-hierarchy taxonomy fields on SkillConfig

**Files changed**: `src/registry/skills.py` — `SkillConfig` gains `role`
(worker|manager|ceo|connector), `division`, and `privilege_class` (read-only|
content|guarded-writer|prod-operator|break-glass), parsed from frontmatter.
`scripts/lint_docs.py` — `check_org_charters()` (11th check): every skill is
claimed by exactly one `.context/org/divisions/<div>/CHARTER.md`.

**Why**: the self-managing agent hierarchy (`.context/org/`, design doc
`docs/superpowers/plans/2026-07-28-management-hierarchy.md`). Division CHARTER.md
is the enforced source of truth for which department owns each agent; the
frontmatter fields are the per-skill declaration.

**Side effects**: none at runtime yet — the fields are declarative; the manager
agents (`system-manager`, `ops-manager`) consume the charters, not these fields.

## 2026-07-27 — Delivery contract in manifest.yml (project segregation Phase A)

**Files changed**: `src/registry/manifest.py` — new `Delivery` / `DeployPolicy`
/ `DeployGate` dataclasses + enums (topology, runtime_clone, autonomy, gate
kinds); `Manifest.delivery` field; `Manifest.from_dict` classmethod that
FILTERS unknown top-level keys instead of passing them to `__init__`.
`scripts/lint_docs.py` — `check_delivery_contracts()` (10th check).
`tests/test_manifest.py` (new, 15), `tests/test_doc_lint.py` (+1).

**Why**: project delivery was prose-only (atlas's single-writer rule lived in
its CLAUDE.md; `app-patch` STEP 0 asked an LLM to notice it). The delivery
block is the machine-readable contract the runner will enforce structurally
(Phase B). See `docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`.

**Bug fixed**: the Python `Manifest.load` TypeError'd on every live manifest
(they carry `mission`/`platforms`/`services`/… keys the dataclass didn't
accept) and `load_all` only caught `ManifestError`, so the whole Python loader
was dead — only the yq-based shell tooling worked. Now tolerant.

**Side effects**: none at runtime yet — a manifest with no `delivery` block
derives the legacy in-place default, so enforcement is opt-in per project.

**Gotchas discovered**: `load_all` must also catch `TypeError`/`YAMLError`,
not just `ManifestError`, or one malformed manifest aborts the whole registry.

## 2026-07-27 — `description` + `subagents` frontmatter fields

**Files changed**: `src/registry/skills.py` — `SkillConfig.description`
(parsed from frontmatter; consumed by the LLM router catalog and by
`runner.agents` as the subagent card) and `SkillConfig.subagents`
(list of skill names to expose as in-session SDK subagents via
`ClaudeAgentOptions(agents=...)`). Isolation comment updated: valid tiers
are `none | workspace | host`; retired `container` parses → workspace.

**Why**: SDK-native agent authoring (docs/SDK_MIGRATION_2026-07-27.md) —
skills stay the single source of truth and now compile into SDK
AgentDefinitions instead of only being system-prompt bodies.

**Side effects**: `runner.llm_router` no longer re-parses SKILL.md YAML for
descriptions (uses the registry field).

## 2026-07-12 — P1: `isolation` frontmatter field

**Files changed**: `src/registry/skills.py` — `SkillConfig.isolation`
(default `"none"`; valid: `none | workspace | container | host`), parsed from
SKILL.md frontmatter. Consumed by `runner.workspaces.resolve_isolation`.

**Why**: skills declare their own isolation tier the same way they declare
model/effort — the frontmatter is the machine contract.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/registry/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


## 2026-04-18 — Add context_files field to SkillConfig

**Files changed**: `src/registry/skills.py` — Added `context_files: list[str]` field to SkillConfig, parsed from SKILL.md frontmatter. Skills can declare which documentation files their sessions should read first, reducing token waste.

## 2026-04-16 — Initial bootstrap (Phase 1)

**Agent task**: Create registry loaders from scratch.

**Files created**:
- `src/registry/skills.py` — SKILL.md frontmatter parser
- `src/registry/manifest.py` — project manifest.yml loader + validator

**Why**: Skills and manifests are the two pieces of declarative configuration
the runner and the registration script read at runtime. Parsers live here so
multiple callers can share them.

**Side effects**: None — new module.

**Gotchas discovered**:
- Frontmatter parsing is tolerant: missing frontmatter, malformed YAML, or
  missing fields all fall through to defaults rather than raising. This keeps
  the system running even when a skill author writes an imperfect SKILL.md.
