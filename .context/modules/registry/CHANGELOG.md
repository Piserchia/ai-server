# Changelog: registry

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
