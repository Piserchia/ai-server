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

### 3.2 Update project CONTEXT.md (when architecture changes)

Update `projects/<slug>/.context/CONTEXT.md` if ANY of these are true:
- You added or removed a module/service
- You changed the data flow between components
- You added or removed an external dependency or API
- You changed hosting config (port, healthcheck, web_root, type)
- You changed the tech stack (new framework, new language)

The 5 standard sections must stay current:
- **Mission**: what the project does, who it's for
- **Platforms**: primary platform + web relationship
- **Web Serving**: how it's exposed on chrispiserchia.com
- **Architecture**: tech stack, key modules, data flow
- **Status**: what works, what's in progress

Do NOT update for minor bug fixes that don't change the architecture.

### 3.3 Update manifest.yml (when hosting changes)

Update `projects/<slug>/manifest.yml` if you changed:
- `type` (static → service, etc.)
- `port` (new or changed port number)
- `healthcheck` (path or removal)
- `start_command` (how the service starts)
- `services` array (added/removed sub-services)
- `web_root` (where static files are served from)

After changing manifest, note in your summary that
`scripts/register-project.sh <slug>` needs to be re-run to update
Caddy and launchd configs.

### 3.4 Record gotchas

If you discovered something surprising, append to
`projects/<slug>/skills/GOTCHAS.md` (create if it doesn't exist):

```markdown
## <short title>

**Symptom**: <what you observed>
**Root cause**: <why it happened>
**Fix/workaround**: <what to do>
```

### 3.5 Server-level docs (note for server-patch)

If your changes affect server-level documentation, note in your summary
what needs updating. Project-scoped sessions cannot modify these directly:
- `projects/_ports.yml` — if you allocated a new port
- `.context/PROJECTS_REGISTRY.md` — if project type or subdomain changed
- Caddy config — if routing changed

### 3.6 Stay in scope

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
