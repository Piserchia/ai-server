---
name: new-project
description: Scaffold, document, deploy, and register a new project from a natural-language description
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, AskUserQuestion]
max_turns: 80
post_review:
  trigger: always
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: max
context_files: [".context/PROJECTS_REGISTRY.md", "projects/_ports.yml", "projects/README.md", ".context/modules/hosting/CONTEXT.md"]
tags: [projects, creation]
---

# New Project

You are creating a new project that will be hosted at `<slug>.chrispiserchia.com`.
This is a two-phase process: **first plan the architecture, then implement it**.
Do not start writing code until you have completed the architecture plan.

## Inputs

Extract from the job description:
- **what**: what the project should do (required)
- **stack**: static | fastapi-service | react-static (optional; infer from description)
- **slug**: project name in kebab-case (optional; derive from description)

If the description is genuinely ambiguous about what to build, use `AskUserQuestion`
once to clarify. Do not ask more than once — make reasonable decisions and document
your assumptions.

## Phase 1: Architecture Planning

Before writing ANY code, produce a structured architecture document. This is the most
important step — a well-planned project is easier to build, easier to maintain, and
easier for future sessions to understand.

Write this plan to `projects/<slug>/.architecture-spec.md` (temporary artifact):

### 1.1 Choose the stack

Evaluate which template fits:
- **static**: Pure HTML/CSS/JS. No backend needed. For: landing pages, tools that run
  entirely client-side, documentation sites.
- **fastapi-service**: Python FastAPI with health endpoint. For: APIs, dashboards with
  data processing, services that need a backend.
- **react-static**: Vite + React compiled to static files. For: interactive UIs,
  single-page applications, complex client-side state.

If the user specified a stack, use it. Otherwise, pick the simplest one that meets the
requirements. Prefer `static` for simple projects, `fastapi-service` for anything needing
server-side logic.

### 1.2 Design the architecture

In the spec document, define:

1. **Purpose statement**: One paragraph explaining exactly what this project does, who
   it's for, and what problem it solves.
2. **File tree**: Every file the project will contain, with a one-line description of each.
3. **Key modules**: For each non-trivial file, describe its responsibility, public
   interface, and dependencies.
4. **Data flow**: How data moves through the system (user input → processing → output).
5. **API design** (services only): Every endpoint with method, path, request/response shapes.
6. **Error handling strategy**: What errors can occur and how each is handled.
7. **Testing strategy**: What to test, what testing tools to use, key test cases.
8. **External dependencies**: Any APIs, libraries, or data sources needed.

### 1.3 Allocate port (services only)

Read `projects/_ports.yml` to find the highest allocated port. Your project gets the
next one. Write it down in the spec.

## Phase 2: Implementation

Now implement the architecture spec file by file.

### 2.1 Copy template

```bash
cp -r skills/new-project/templates/<stack>/ projects/<slug>/
```

### 2.2 Fill placeholders

Replace all `<PLACEHOLDER>` markers in the template files:
- `<SLUG>` → project slug (kebab-case)
- `<NAME>` → human-readable project name
- `<MISSION>` → one-line mission statement
- `<DESCRIPTION>` → short description
- `<PORT>` → allocated port number (services only)
- `<TODAY>` → today's date (YYYY-MM-DD)

### 2.3 Build the project

Implement the actual project code according to your architecture spec:

- **Write clean, production-quality code.** This is not a prototype. Include proper
  error handling, input validation at system boundaries, and meaningful variable names.
- **Follow the architecture spec exactly.** Every file in your file tree should exist.
  Every endpoint should be implemented. Every error case should be handled.
- **Write tests.** At minimum: health endpoint test (services), core logic tests, one
  integration test if applicable.
- **For react-static**: After writing code, run `npm install && npm run build` to
  generate the `dist/` directory.

### 2.4 Update documentation

Customize the template docs to accurately reflect what you built:
- `.context/CONTEXT.md` — update Architecture section with actual modules, data flow
- `CLAUDE.md` — add project-specific instructions if needed
- `.context/CHANGELOG.md` — already has bootstrap entry from template

### 2.5 Initialize git and create GitHub repo

```bash
cd projects/<slug>
git init -b main
git add -A
git commit -m "Initial scaffold via new-project skill"
gh repo create Piserchia/<slug> --private --source=. --remote=origin --push
```

If `gh repo create` fails (e.g., name taken), report it in the summary. The project
is still functional locally.

### 2.6 Update port registry

Append your port allocation to `projects/_ports.yml` (at the ai-server root, NOT in
the project directory):
```yaml
<PORT>: <slug>
```

### 2.7 Register with hosting

```bash
cd "$HOME/Library/Application Support/ai-server"
bash scripts/register-project.sh <slug>
```

This creates the Caddy snippet, launchd plist (services), DB row, and runs the
healthcheck probe.

### 2.8 Update projects registry

Append a row to `.context/PROJECTS_REGISTRY.md` in the "Currently hosted" table.

### 2.9 Delete the architecture spec

```bash
rm projects/<slug>/.architecture-spec.md
git -C projects/<slug> add -A && git -C projects/<slug> commit -m "Remove architecture spec (build complete)"
git -C projects/<slug> push origin main
```

## Quality gate

Before finishing, verify ALL of these:

- [ ] Project directory exists at `projects/<slug>/` with all planned files
- [ ] `manifest.yml` exists and is valid YAML with all required fields
- [ ] `.context/CONTEXT.md` has all 5 standard sections (Mission, Platforms, Web Serving, Architecture, Status)
- [ ] `.git/` exists — project has its own git repo
- [ ] GitHub repo created (or failure documented)
- [ ] `register-project.sh` ran successfully
- [ ] For services: `curl http://localhost:<port>/health` returns 200
- [ ] For static: the main HTML file exists and is well-formed
- [ ] `projects/_ports.yml` updated (services only)
- [ ] `.context/PROJECTS_REGISTRY.md` updated
- [ ] Tests pass (if any)

If any check fails, fix it. After 3 fix attempts on the same issue, document it in
the summary and move on.

## Gotchas

- `projects/` directories are gitignored by ai-server's `.gitignore`. Each project is
  its own repo. Never `git add` from the ai-server root for project files.
- `register-project.sh` expects `manifest.yml` at the project root. Verify it exists
  before calling.
- Port allocation: read `_ports.yml` BEFORE choosing a port. Never reuse a port.
- For react-static: `web_root: dist` in manifest means Caddy serves from `projects/<slug>/dist/`.
  You MUST run `npm run build` to create the `dist/` directory.
- The `gh` CLI uses `Piserchia` as the GitHub org. If the repo already exists, skip
  creation and just add the remote.
- `ANTHROPIC_API_KEY` must never appear in any project code or `.env`. This server
  uses subscription auth.
