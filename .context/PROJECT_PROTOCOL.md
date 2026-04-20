# Project Protocol

This protocol applies to all project-scoped sessions — sessions whose working
directory is `projects/<slug>/` rather than the ai-server root. Skills like
`app-patch` and `new-project` are project-scoped.

The server-level `PROTOCOL.md` does NOT apply inside projects. This file is the
project-level equivalent.

---

## Phase 1: Orient (before any code changes)

### 1.1 Read project context

Every project follows a standard layout. Read these files (all are optional;
skip any that don't exist):

```
projects/<slug>/CLAUDE.md              # Project-specific instructions
projects/<slug>/.context/CONTEXT.md    # Architecture: Mission, Platforms, Web Serving, Architecture, Status
projects/<slug>/.context/CHANGELOG.md  # Change history (newest first)
projects/<slug>/manifest.yml           # Hosting config (type, port, healthcheck)
```

### 1.2 Check for gotchas

If `projects/<slug>/skills/GOTCHAS.md` exists, read it. These are hard-won
lessons from prior sessions working on this project.

### 1.3 Understand the hosting setup

For services: note the port and healthcheck path from `manifest.yml`.
For static sites: note the `web_root` (usually `.` or `dist/`).

---

## Phase 2: Execute (make changes)

Work normally. Keep a mental log of:
- What files you modified and why
- Surprising behavior or assumptions that broke
- Patterns worth documenting for future sessions

---

## Phase 3: Write-back (after changes, before finishing)

### 3.1 Update project CHANGELOG.md

Append an entry to `projects/<slug>/.context/CHANGELOG.md`:

```markdown
## YYYY-MM-DD — <short summary>

**What changed**: <list of files and specific modifications>
**Why**: <the reasoning — not just "fixed bug" but why it was broken>
**How to verify**: <one sentence — curl, open browser, run test>
```

### 3.2 Update project CONTEXT.md (if needed)

Update `projects/<slug>/.context/CONTEXT.md` if any of these changed:
- The project's purpose or scope
- Its architecture (new modules, changed data flow)
- Its external dependencies or API surface
- Its hosting configuration (port, healthcheck, web_root)

Do NOT update for minor bug fixes that don't change the architecture.

### 3.3 Record gotchas

If you discovered something surprising, append to
`projects/<slug>/skills/GOTCHAS.md` (create if it doesn't exist):

```markdown
## <short title>

**Symptom**: <what you observed>
**Root cause**: <why it happened>
**Fix/workaround**: <what to do>
```

### 3.4 Stay in scope

Project-scoped sessions must NOT:
- Modify files outside `projects/<slug>/` (except `_ports.yml` and
  `PROJECTS_REGISTRY.md` during project creation)
- Modify server code in `src/`
- Modify server-level `.context/` files
- Run git commands in the ai-server root (each project is its own git repo)

If the fix requires server-side changes, document the need in your summary
and leave it for a `server-patch` job.

---

## Quality standards

### CHANGELOG entries must include:
- What changed (files and specific modifications)
- Why it changed (reasoning, not just "fixed bug")
- How to verify (curl command, browser check, test command)

### Project context must stay:
- Accurate (update when architecture changes)
- Concise (reference doc, not a novel)
- In the standard 5-section format (Mission, Platforms, Web Serving,
  Architecture, Status)
