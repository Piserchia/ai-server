# Documentation Index

> For any new Claude session: read this file to know what exists and where to look.
> Last updated: 2026-04-18

## Quick navigation

| I need to... | Read these |
|---|---|
| Understand the overall system | `SERVER.md`, `.context/SYSTEM.md` |
| Work on server code (src/) | `.context/modules/<module>/CONTEXT.md`, `.context/PROTOCOL.md` |
| Work on a specific project | `projects/<slug>/CLAUDE.md`, `.context/PROJECT_PROTOCOL.md` |
| Add a new project | `.context/PROJECTS_REGISTRY.md`, `skills/new-project/SKILL.md` |
| Add a new skill | `.context/SKILLS_REGISTRY.md`, `skills/new-skill/SKILL.md` |
| Patch a project | `skills/app-patch/SKILL.md` (reads project's own CLAUDE.md) |
| Patch server code | `skills/server-patch/SKILL.md` (always PR-gated) |
| Debug a failure | `docs/Troubleshooting.md`, `volumes/audit_log/<job_id>.jsonl` |
| Understand a skill | `skills/<name>/SKILL.md` (frontmatter = config, body = system prompt) |
| Check what's hosted | `.context/PROJECTS_REGISTRY.md` |
| Check what skills exist | `.context/SKILLS_REGISTRY.md` |
| Review system performance | `src/runner/retrospective.py`, `skills/review-and-improve/SKILL.md` |
| Understand hosting setup | `.context/modules/hosting/CONTEXT.md`, `Caddyfile` |

## Documentation hierarchy

```
CLAUDE.md                           ← Root session directive (auto-loaded)
SERVER.md                           ← Architecture overview for humans
.context/
  INDEX.md                          ← This file (navigation map)
  SYSTEM.md                         ← Module graph, conventions, invariants
  PROTOCOL.md                       ← Write-back protocol (server-scoped, mandatory)
  PROJECT_PROTOCOL.md               ← Write-back protocol (project-scoped)
  PROJECTS_REGISTRY.md              ← Index of hosted projects
  SKILLS_REGISTRY.md                ← Index of installed skills
  modules/
    runner/   CONTEXT.md, CHANGELOG.md, skills/PATTERNS.md
    gateway/  CONTEXT.md, CHANGELOG.md
    db/       CONTEXT.md, CHANGELOG.md
    registry/ CONTEXT.md, CHANGELOG.md
    hosting/  CONTEXT.md, CHANGELOG.md
docs/
  Troubleshooting.md                ← Failure modes + fixes
  PHASE_3_PLAN.md through PHASE_6_PLAN.md  ← Historical (all shipped)
  README.md                         ← Reading order guide
skills/<name>/
  SKILL.md                          ← Frontmatter (config) + body (system prompt)
projects/<slug>/
  CLAUDE.md                         ← Project session directive
  manifest.yml                      ← Machine-readable hosting config
  .context/CONTEXT.md               ← Standard format: Mission, Platforms, Web Serving, Architecture, Status
  .context/CHANGELOG.md             ← Project-level change history
```

## Key conventions

- **SKILL.md frontmatter is the machine contract** — model, effort, tools, post_review settings
- **SKILL.md body is the system prompt** — instructions to Claude, not documentation
- **CHANGELOG.md is institutional memory** — every code-touching session appends
- **PROTOCOL.md is immutable** — never modify without explicit human request
- **Phase plans are historical** — all 6 phases shipped; plans document what was planned vs what happened

## Update this file

When you add a new documentation file, add it to this index.
