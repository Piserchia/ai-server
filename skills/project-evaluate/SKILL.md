---
name: project-evaluate
description: Evaluate an existing project and produce manifest.yml + .context/CONTEXT.md in the standard documentation format
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
max_turns: 40
post_review:
  trigger: always
context_files: [".context/PROJECTS_REGISTRY.md", ".context/modules/hosting/CONTEXT.md"]
tags: [projects, documentation]
---

# Project Evaluate

You are evaluating an existing project codebase and producing its standard
documentation set: `manifest.yml`, `.context/CONTEXT.md`, `CLAUDE.md`, and
`.context/CHANGELOG.md`. The goal is to make the project fully self-describing
so that future agent sessions, hosting scripts, and human readers can
understand it immediately.

## Inputs you will receive

Extract from the job description or `payload`:
- **project_slug** (required): the directory name under `projects/`. Typically
  appears as "evaluate project <slug>" or in `payload.project_slug`.

If the slug is genuinely ambiguous (e.g., description says "evaluate the app"
with no project name), use `AskUserQuestion` once to ask which project. Do not
ask more than one clarifying question.

## Procedure

### 1. Identify project path

Resolve `projects/<slug>/`. Verify it exists:
```bash
ls -la projects/<slug>/
```
If the directory does not exist, list available projects with `ls projects/`
and report the error. Do not proceed with a nonexistent project.

### 2. Read existing docs

Check for existing documentation files:
```bash
ls projects/<slug>/manifest.yml projects/<slug>/.context/CONTEXT.md projects/<slug>/CLAUDE.md projects/<slug>/.context/CHANGELOG.md 2>/dev/null
```
Note which files exist and which need to be created. For files that already
exist, read their current content — you will compare against your proposed
versions later.

### 3. Analyze codebase

Read the project's source code thoroughly. You must understand the project
well enough to write an accurate mission statement and architecture summary.

Check for (in this order):
- **Entry points**: `main.py`, `app.py`, `index.html`, `index.js`,
  `package.json` `main` field, `pyproject.toml` scripts
- **Configuration**: `requirements.txt`, `Pipfile`, `package.json`,
  `pyproject.toml`, `Gemfile`, `Cargo.toml`, `go.mod`
- **Architecture**: directory structure (`ls -R` or `find . -type f`),
  key modules, internal imports
- **API / routes**: look for Flask/FastAPI/Express route decorators,
  URL patterns, endpoint definitions
- **Static assets**: HTML, CSS, JS in public/static/dist directories
- **Tests**: `tests/`, `test_*.py`, `*.test.js`, `spec/`
- **Environment**: `.env.example`, `docker-compose.yml`, `Dockerfile`
- **Existing README**: `README.md` often contains setup instructions
  and purpose statements

### 4. Determine hosting config

From the code analysis, determine:

- **`type`**: `static` (HTML/CSS/JS served as files), `service` (long-running
  process with a port), or `api` (headless API service)
- **`port`**: for services — look for `app.run(port=...)`,
  `uvicorn.run(..., port=...)`, `listen(PORT)`, or similar
- **`healthcheck`**: look for `/health`, `/healthz`, `/api/health` endpoints.
  If none exists, use `/` for static sites or note it as missing for services.
- **`start_command`**: how to start the service (e.g., `python main.py`,
  `uvicorn app:app --port 8080`, `npm start`)
- **`subdomain`**: derive from slug (e.g., `market-tracker` ->
  `market-tracker.chrispiserchia.com`)
- **`web_strategy`**:
  - `native-web` — the project IS a web application
  - `legacy-shim` — temporary web version of a non-web project
  - `companion` — web companion interface for a native app
  - `planned` — web serving not yet implemented
- **`platforms.primary`**: `ios`, `web`, `cli`, `api`, or `library`
- **`platforms.web`**: `native`, `planned`, or `not-applicable`

### 5. Generate manifest.yml

Write `projects/<slug>/manifest.yml` following this schema:

```yaml
slug: <slug>
name: <Human-readable Name>
mission: "<What the project does and who it's for — NOT how it's built>"
type: static|service|api
subdomain: <slug>
web_strategy: native-web|legacy-shim|companion|planned
platforms:
  primary: <ios|web|cli|api|library>
  web: <native|planned|not-applicable>

# Service/API only:
port: <int>
healthcheck: <path>
start_command: "<command>"

# Static only:
web_root: <subdirectory>

# If the project has multiple sub-services:
# services:
#   - name: <service-name>
#     port: <int>
#     start_command: "<command>"
#     healthcheck: <path>
#     path_prefix: <caddy handle_path prefix>
#     api_routes: [<glob>]

# Optional:
# env_required: [VAR1, VAR2]
# env_optional: [VAR3]

git:
  remote: <origin URL or "local-only">
```

The `mission` field must describe WHAT the project does and WHO it's for.
Do not describe HOW it's built. Bad: "A Python FastAPI service with SQLAlchemy".
Good: "Live MLB bingo card generator for baseball fans watching games together".

### 6. Generate .context/CONTEXT.md

Create `projects/<slug>/.context/CONTEXT.md` with these five mandatory sections:

```markdown
# <Project Name>

## Mission

<2-3 sentences: what the project does, who it's for, what problem it solves.
This should match the manifest.yml mission but with more detail.>

## Platforms

- **Primary**: <platform> — <brief description of the primary experience>
- **Web**: <native|planned|not-applicable> — <how web fits in>

## Web Serving

- **Subdomain**: `<slug>.chrispiserchia.com`
- **Strategy**: <web_strategy value> — <one sentence explaining the choice>
- **Type**: <static|service|api>
<If service/api:>
- **Port**: <port>
- **Health**: `<healthcheck path>`
- **Start**: `<start_command>`

## Architecture

- **Stack**: <language(s), framework(s), key libraries>
- **Structure**:
  - `<path>` — <what it does>
  - `<path>` — <what it does>
  - ...
- **Data flow**: <brief description of how data moves through the system>
<If applicable:>
- **External services**: <APIs, databases, etc.>

## Status

- **Working**: <what's functional today>
- **Planned**: <known next steps, TODOs, issues>
- **Gaps**: <what's missing — tests, docs, error handling, etc.>
```

### 7. Generate CLAUDE.md

Create `projects/<slug>/CLAUDE.md` — a short session directive:

```markdown
# CLAUDE.md — <Project Name>

You are working inside the `<slug>` project.

1. Read `.context/CONTEXT.md` for architecture and current status.
2. Read `manifest.yml` for hosting configuration.
3. Check `.context/CHANGELOG.md` for recent changes.

## Project-specific rules

<Any project-specific conventions discovered during analysis,
or "None yet — this project was just onboarded." if nothing notable.>
```

### 8. Generate .context/CHANGELOG.md

Create `projects/<slug>/.context/CHANGELOG.md`:

```markdown
# Changelog: <Project Name>

<!-- Reverse chronological. Newest entries at the top. -->

## YYYY-MM-DD — Project documentation bootstrapped

**Agent task**: Evaluate project and produce standard documentation
**Files created**:
- `manifest.yml` — hosting configuration
- `.context/CONTEXT.md` — project context document
- `.context/CHANGELOG.md` — this changelog
- `CLAUDE.md` — session directive

**Why**: Onboarding project into the ai-server documentation standard so it
can be registered for hosting and understood by future agent sessions.
```

Use today's actual date, not a placeholder.

### 9. Non-destructive check

**Critical**: If ANY of the target files already exist, you must not silently
overwrite them. For each existing file:

1. Show the diff between the existing content and your proposed content
2. Use `AskUserQuestion` to confirm: "File `<path>` already exists. Here's
   what would change: <summary>. Overwrite? (yes/no)"
3. If the user says no, skip that file and note it in your summary

Only overwrite files the user explicitly approves.

### 10. Commit

Stage and commit the documentation files to the project's own git repo
(NOT the ai-server root):

```bash
cd projects/<slug>
git add manifest.yml .context/ CLAUDE.md
git commit -m "Add project documentation via project-evaluate"
```

If the project has a remote, push:
```bash
git push origin HEAD 2>/dev/null || echo "No remote or push failed — local commit only"
```

### 11. Summary

Your final text message must report:
- What files were generated (and which were skipped due to existing content)
- Key findings about the project (tech stack, architecture highlights)
- Whether the project is ready for `register-project.sh`
- Any concerns (missing healthcheck, no tests, unclear purpose, etc.)

## Quality gate

Before writing your summary, verify:

- [ ] `manifest.yml` is valid YAML with all required fields (`slug`, `name`,
      `mission`, `type`, `subdomain`, `web_strategy`, `platforms`)
- [ ] `.context/CONTEXT.md` has all 5 standard sections (Mission, Platforms,
      Web Serving, Architecture, Status)
- [ ] Mission statement accurately reflects the project's purpose — describes
      WHAT and WHO, not HOW
- [ ] Web serving strategy is correctly identified (`native-web` for web apps,
      `companion` for native apps with a web UI, `planned` for no web yet, etc.)
- [ ] No existing documentation was overwritten without user confirmation
- [ ] Files are committed to the project's git repo, not the ai-server root

If any check fails, fix it before finishing. If after 3 attempts a check still
fails, note the limitation in your summary.

## Gotchas (living section -- append when you learn something)

- Each project in `projects/` is its OWN git repo, separate from ai-server.
  Always `cd projects/<slug>` before running git commands. Committing at the
  server root would pollute the server repo with project files.
- The `mission` field is the most important field in the manifest. It should
  describe WHAT the project does and WHO it's for, not HOW it's built.
  "A Python FastAPI service" is not a mission. "Live sports scores for fans"
  is a mission.
- `web_strategy` values: `native-web` (project IS a web app), `legacy-shim`
  (temporary web wrapper for a non-web project), `companion` (web companion
  for a native app), `planned` (web serving not yet implemented).
- Read `.context/modules/hosting/CONTEXT.md` for the full manifest schema
  before generating — the schema may have evolved since this skill was written.
- For multi-service projects (e.g., a frontend + API), the manifest should
  use the `services` array. Each sub-service gets its own `port`,
  `start_command`, `healthcheck`, and `path_prefix`.
- Static sites need `web_root` instead of `port`/`healthcheck`/`start_command`.
- If the project has no git repo yet, initialize one:
  `cd projects/<slug> && git init -q`

## Files this skill creates or updates

- `projects/<slug>/manifest.yml`
- `projects/<slug>/.context/CONTEXT.md`
- `projects/<slug>/.context/CHANGELOG.md`
- `projects/<slug>/CLAUDE.md`
