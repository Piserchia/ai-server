# Changelog: registry

<!-- Newest entries at top. Every session that modifies this module appends here. -->

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
