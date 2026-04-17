# Phase 4 — Expansion skills

> **For the Claude Code session executing this**: this phase is big. Build the
> skills in the order listed — each one builds on its predecessors. Every
> skill ships with its SKILL.md + any support files + a test (in `tests/`)
> for the non-prompt parts.

## Goal

Turn the system from "manually registered projects" into "describe what you
want, the system builds it, documents it, tests it, hosts it, and can patch
it later."

Six new skills + two MCP servers + automated post-review on code-touching
jobs + event-triggered self-diagnose on repeated failures.

## Done =

All of these work end-to-end via `/task`:

1. `/task new project: <description>` → scaffolded, registered, live at
   `<slug>.<domain>`, DM'd with URL, within 10 minutes.
2. `/task fix <project>: <issue>` → patches the project, reviews the diff,
   commits/pushes to its repo, restarts service if needed, DMs confirmation.
3. `/task new skill: <description>` → drafts SKILL.md, runs code-review
   sub-agent, merges (if LGTM) to this repo, appends to SKILLS_REGISTRY.md,
   DMs you.
4. `/task diagnose <issue>` → reads audit logs + service logs, outputs
   structured diagnosis + proposed fix, applies if low-risk, opens PR otherwise.
5. A job that fails twice in 10 minutes automatically enqueues a
   `self-diagnose` job — you wake up to a diagnosis already done.
6. Every `app-patch`, `new-project`, and `server-patch` job auto-spawns a
   `code-review` sub-agent after the main session. If the reviewer says
   `blocker`, the job goes to `awaiting_user` and Telegram alerts you.

## Status

Not started. Phase 3 is the prerequisite — the `new-project` skill depends on
`register-project.sh` working.

## Decisions locked in

1. **Each skill has its own `SKILL.md` + optional support files** (templates, examples). No cross-skill dependencies except via the shared MCP tools below.
2. **Code-review runs as a sub-agent in `plan` mode** (read-only). Its output is parsed by the runner and stored as `jobs.review_outcome`.
3. **Auto-merge policy per MISSION.md**: skills auto-merge on `code-review` LGTM; server code always manual-merge; projects are owned by you, so `app-patch` commits-and-pushes without merge gate (the project repo is a separate repo — if you don't like the change, you revert it there).
4. **Event triggers live in the runner's `_cancel_listener` process** (renamed to `_event_listener` since it'll do more now). Subscribes to `jobs:done:*` pub/sub in addition to `jobs:cancel`.
5. **MCP servers are in-process** via `create_sdk_mcp_server()`. No extra processes.
6. **Templates for new-project live in `skills/new-project/templates/`**: one `.tar.gz` per supported stack (static, fastapi-service, nodejs-service, react-static).

## Open decisions (Chris must resolve)

### 1. Which project stacks should `new-project` support out of the box?

Minimum viable: `static` (HTML/CSS/JS), `fastapi-service` (Python). Everything else can come later as the `new-skill` flow adds templates.

Candidates:
- `static` — HTML + vanilla JS/CSS ✓
- `fastapi-service` — Python FastAPI + uvicorn ✓
- `react-static` — Vite + React compiled to static files
- `nodejs-service` — Node.js Express or similar
- `python-cli` — just a script, no server (would be type=tool or similar; not all projects need hosting)

**Recommendation**: start with `static` + `fastapi-service` in Phase 4; add others via `new-skill` as the need arises.

### 2. What does "fix a project" actually commit?

Options:
- **A. Direct commit + push to main** on the project's repo. Fast, matches "you own the project repo."
- **B. PR-and-manual-merge**. Safer but slower; adds friction.
- **C. Direct commit to a branch + open PR**. Compromise: changes visible before merge, but no blocking merge gate.

**Recommendation**: C by default, configurable per-project in manifest.yml (`patch_mode: direct | branch | pr`).

### 3. Which model for `new-project` scaffolding?

Originally designed as Sonnet 4.6 / medium (scaffolding is mostly file creation). But coding-intent routing in Phase 2's router matches `new-project` only via explicit "new project:" prefix, so the coding-heavy path (Opus) isn't triggered.

If new-project keeps being too shallow (missing error handling, weak tests in scaffolded code), escalate to Opus 4.7 / medium as the default. Chris should decide after Phase 4 runs a few new projects.

**Leaving at Sonnet / medium for start, Opus / high as escalation on_failure.**

### 4. How much should `self-diagnose` be allowed to auto-apply?

Risk tiers per design:
- **Very low risk** (auto-apply): restart a service, clear a lock file, truncate a log.
- **Low risk** (auto-apply + notify): change a config value, tweak a scheduled cron.
- **Medium risk** (Telegram Y/N): patch a project.
- **High risk** (PR gate): patch server code.

**Recommendation**: `self-diagnose` only auto-applies very-low-risk. Anything else delegates to `app-patch` or `server-patch` which have their own policies. This keeps the autonomy surface tight.

---

## Architecture refresher

Three new concerns showing up in Phase 4:

### A. Sub-agent pattern (parent job spawns child job in-process)

The `code-review` reviewer isn't a separate CLI process — it's another
`ClaudeSDKClient` session started from within the parent. Parent session
completes its work, then (before the parent's `_process_job` returns success)
the runner spawns the review session on the diff, waits for its result,
stamps `jobs.review_outcome` on the parent, then decides whether to mark
success or `awaiting_user`.

Implementation: `src/runner/review.py` exposes `run_code_review(parent_job, diff) -> ReviewOutcome`. Called from `_process_job` after `run_session` returns.

### B. Event-triggered jobs

Runner process subscribes to `jobs:done:*`. For each done event, checks a
small rules engine:

- "same skill failed 2 times in 10 min" → enqueue self-diagnose for the failing skill
- "same project healthcheck failed 3 consecutive" → enqueue self-diagnose for the project
- "daily spend > 80% of cap" → Telegram alert (Phase 5 hook, noted here)

Rules live in `src/runner/events.py`. Evaluated against recent Postgres job
rows (cheap SQL; no sliding-window state needed).

### C. In-process MCP servers

`create_sdk_mcp_server()` from the SDK. Two servers for Phase 4:

- `projects` — tools: `list_projects`, `get_project`, `restart_project`, `read_manifest`, `read_project_logs`
- `dispatch` — tool: `enqueue_job(kind, description, payload)` — lets a parent skill spawn a child skill asynchronously (as opposed to the synchronous sub-agent pattern for code-review)

Both passed as custom tools to relevant skills' `ClaudeAgentOptions`.

---

## File-by-file plan

### Order of implementation (follow strictly)

1. **`src/runner/review.py`** — sub-agent runner for code-review (no skill yet; this is the plumbing)
2. **`skills/code-review/SKILL.md`** — the prompt that defines review criteria
3. **Integrate code-review into `_process_job`** — call after successful sessions for qualifying job kinds
4. **`skills/new-project/SKILL.md`** + `templates/static.tar.gz` + `templates/fastapi-service.tar.gz`
5. **`skills/app-patch/SKILL.md`**
6. **`skills/new-skill/SKILL.md`**
7. **In-process MCP servers: `src/runner/mcp_projects.py`, `src/runner/mcp_dispatch.py`**
8. **`skills/self-diagnose/SKILL.md`**
9. **`src/runner/events.py`** — event-triggered rules engine
10. **Wire `events.py` into the runner** (subscribe to `jobs:done:*`, evaluate rules)
11. **Tests** for every pure-function piece (reviewer output parser, events rules, MCP tool handlers)

### 1. `src/runner/review.py`

Reviewer runs on a diff. Input: parent job, diff string (from `git diff`).
Output: `ReviewOutcome { outcome: LGTM|changes_requested|blocker, notes: str }`.

Key behaviors:
- Uses Opus 4.7 / high / `permission_mode=plan` so it literally cannot modify files
- Max 5 turns (reviews should be fast)
- Feeds the diff inline as user prompt; doesn't need file reading in most cases
- Parses Claude's final text block for the outcome marker. Convention: final text starts with one of `LGTM`, `CHANGES`, or `BLOCKER` (all caps), followed by prose.
- If parsing fails, defaults to `changes_requested` (safe default)

Sketch:

```python
# src/runner/review.py

from dataclasses import dataclass
from typing import Literal

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, AssistantMessage, TextBlock

from src import audit_log
from src.models import Job

ReviewOutcomeLiteral = Literal["LGTM", "changes_requested", "blocker"]


@dataclass
class ReviewOutcome:
    outcome: ReviewOutcomeLiteral
    notes: str


REVIEWER_SYSTEM_PROMPT = """You are reviewing a diff produced by another Claude
session. Your job is to say whether the change is safe to keep, needs
revisions, or must be rolled back.

Start your response with EXACTLY ONE of these markers on the first line:
- LGTM              — change is correct, tests exist, no concerns
- CHANGES           — change has issues but nothing catastrophic; list what to fix
- BLOCKER           — change would break something important; must not be kept

After the marker, write 2-5 sentences of rationale. Keep it tight.

Evaluate for:
- Correctness (does it do what the task asked?)
- Safety (could this corrupt data, leak secrets, break auth?)
- Test coverage (is new logic tested?)
- Consistency with existing patterns in the codebase
- Documentation hygiene (CHANGELOG updated for modules touched?)

You CANNOT run commands, read files, or edit anything — you are in plan mode.
Reason purely from the diff and any context the parent provided."""


async def run_code_review(parent_job: Job, diff: str, cwd: str) -> ReviewOutcome:
    options = ClaudeAgentOptions(
        cwd=cwd,
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        allowed_tools=[],  # none — reasoning only
        permission_mode="plan",
        model="claude-opus-4-7",
        effort="high",
        max_turns=3,
        session_id=f"{parent_job.id}-review",
    )
    prompt = (
        f"Parent job: {str(parent_job.id)[:8]} ({parent_job.resolved_skill or parent_job.kind})\n"
        f"Task description: {parent_job.description[:500]}\n\n"
        f"Diff to review:\n\n```diff\n{diff[:50000]}\n```"
    )

    audit_log.append(str(parent_job.id), "code_review_started")
    full_text = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        full_text.append(b.text)

    text = "\n".join(full_text).strip()
    outcome = _parse_outcome(text)
    audit_log.append(
        str(parent_job.id), "code_review_done",
        outcome=outcome.outcome,
        notes=outcome.notes[:500],
    )
    return outcome


def _parse_outcome(text: str) -> ReviewOutcome:
    first_line = text.split("\n", 1)[0].strip().upper()
    rest = text.split("\n", 1)[1].strip() if "\n" in text else ""
    if first_line.startswith("LGTM"):
        return ReviewOutcome("LGTM", rest)
    if first_line.startswith("BLOCKER"):
        return ReviewOutcome("blocker", rest)
    if first_line.startswith("CHANGES"):
        return ReviewOutcome("changes_requested", rest)
    # Default safe: treat as changes_requested
    return ReviewOutcome("changes_requested", f"(parser fallback) {text[:500]}")
```

**Tests** (`tests/test_review.py`):
- `_parse_outcome("LGTM\nAll good")` → `LGTM`
- `_parse_outcome("BLOCKER\nThis will break auth")` → `blocker`
- `_parse_outcome("CHANGES\nTests missing")` → `changes_requested`
- `_parse_outcome("Looks good I guess?")` → `changes_requested` (parser fallback)

### 2. `skills/code-review/SKILL.md`

The actual *skill* that wraps `run_code_review` for when it's user-triggered
(`/task review the diff at <path>`). When sub-agent-triggered, the runner
calls `run_code_review` directly without routing through the skill loader.
The SKILL.md exists for the user-triggered path.

```markdown
---
name: code-review
description: Review a diff or a proposed change; say LGTM / CHANGES / BLOCKER with rationale.
model: claude-opus-4-7
effort: high
permission_mode: plan
required_tools: [Read, Glob, Grep]
max_turns: 5
tags: [internal-or-user, review]
---

# Code review

You are reviewing a change. ...
[copy of REVIEWER_SYSTEM_PROMPT body, adapted for user-triggered context where
the user might reference a path rather than pasting a diff]
```

### 3. Integrate into `_process_job`

```python
# src/runner/main.py — add after successful result:

# Post-review for code-touching skills
POST_REVIEW_KINDS = {"new-project", "app-patch", "server-patch"}
if job.resolved_skill in POST_REVIEW_KINDS:
    try:
        diff = _get_git_diff(cwd)
        if diff:
            review = await review_mod.run_code_review(job, diff, str(cwd))
            async with session_scope() as s:
                await s.execute(
                    update(Job).where(Job.id == job.id).values(review_outcome=review.outcome)
                )
            if review.outcome == "blocker":
                # Mark awaiting_user, Telegram alert, do not continue
                await _finish_job(job.id, JobStatus.awaiting_user, error=f"code-review blocker: {review.notes[:500]}")
                return
            # CHANGES outcome: log it, proceed (user can see it in the dashboard)
    except Exception:
        log.exception("code-review failed (non-fatal)")
```

### 4. `skills/new-project/SKILL.md` + templates

The most complex skill. Drives the whole pipeline from description to live URL.

```markdown
---
name: new-project
description: Scaffold, document, commit, host a new project from a natural-language description.
model: claude-sonnet-4-6
effort: medium
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, AskUserQuestion]
max_turns: 60
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
post_review:
  trigger: always
tags: [projects, creation]
---

# New Project

You are creating a new project: a directory under `projects/<slug>/` with code,
a manifest, a .context/ hierarchy, and a live public URL.

## Inputs (from description + payload)

- A description of what the project does
- Optionally in payload: `stack` (static|fastapi|nodejs), `slug` (if not given, derive from description)

## Procedure

### Step 1 — Plan

Decide:
- **Stack**: static (HTML-only) | fastapi-service (Python service) | api (JSON API).
  If unclear, use AskUserQuestion ONCE.
- **Slug**: 2-4 lowercase words with hyphens. Derive from description; if similar slug exists in projects/, suffix with -2.
- **Subdomain**: same as slug by default.
- **Port** (if service/api): read `projects/_ports.yml`, pick the next unused port in 9001-9999 range.

### Step 2 — Scaffold

Copy the matching template from `skills/new-project/templates/`:

```bash
mkdir -p projects/<slug>
cd projects/<slug>

# Untar the template
tar -xzf ../../skills/new-project/templates/<stack>.tar.gz -C .
```

Then fill in placeholders:
- `<SLUG>` → the slug
- `<SUBDOMAIN>` → the subdomain
- `<PORT>` → the port (service/api only)
- `<DESCRIPTION>` → one-line description
- `<TODAY>` → today's date

Customize the scaffolded code to actually do what the description says.
This is the craft part — not copy-paste-and-rename, but actually implementing
what the user asked for.

### Step 3 — Initialize git + GitHub repo

```bash
cd projects/<slug>
git init -b main
git add -A
git commit -m "Initial scaffold: <description>"
gh repo create Piserchia/<slug> --private --source=. --remote=origin --push
```

### Step 4 — Register with hosting

```bash
cd <server-root>
bash scripts/register-project.sh <slug>
```

This generates the Caddy snippet, installs launchd plist (service/api only),
inserts DB row, runs a healthcheck probe.

### Step 5 — Update registries

Append to `.context/PROJECTS_REGISTRY.md`:
```markdown
| `<slug>` | <type> | `<subdomain>.<domain>` | `github.com/Piserchia/<slug>` | <current phase> |
```

Update `projects/_ports.yml` if a port was claimed.

### Step 6 — Final summary

Your final text block is the TL;DR for the Telegram DM. Include:
- URL: `https://<subdomain>.<domain>`
- What it does (1-2 sentences)
- GitHub repo URL
- Any manual steps the user should take (e.g., "add env var X to projects/<slug>/.env")

## Quality gate

Before finishing:
- [ ] `projects/<slug>/manifest.yml` exists and validates via `yq` without errors
- [ ] `projects/<slug>/.context/{CONTEXT.md, CHANGELOG.md}` exist
- [ ] `projects/<slug>/.git` exists
- [ ] GitHub repo `Piserchia/<slug>` exists and has the initial commit pushed
- [ ] `scripts/register-project.sh` exited successfully
- [ ] Healthcheck succeeded (if service/api type)
- [ ] `https://<subdomain>.<domain>` returns 200 (via `curl -I -m 10`)
- [ ] `.context/PROJECTS_REGISTRY.md` updated
- [ ] `projects/_ports.yml` updated if port claimed

If any check fails, surface it in your final summary; don't pretend it worked.

## Gotchas

- `gh repo create --source=. --push` fails if origin remote already exists. Check first: `git remote get-url origin 2>/dev/null && echo "origin exists"`.
- Caddy reload can take ~1 second for the new cert to issue on first request. Retry the healthcheck 2-3 times if the first attempt fails.
- Some stacks have start commands that daemonize (Node's `forever`). The launchd plist assumes foreground. Use `npm start` or similar that stays attached.
```

**Template structure** (`skills/new-project/templates/static.tar.gz`):
```
index.html           (minimal HTML with <SLUG> / <DESCRIPTION> placeholders)
assets/style.css
manifest.yml         (with <PORT> absent, <TYPE>=static)
CLAUDE.md
.context/
  CONTEXT.md
  CHANGELOG.md
  skills/
    (empty)
README.md
.gitignore           (node_modules/, __pycache__/, etc.)
```

**Template** (`skills/new-project/templates/fastapi-service.tar.gz`):
```
main.py              (minimal FastAPI with / and /health endpoints, reads PORT env var)
pyproject.toml
.env.example
manifest.yml         (type=service, port=<PORT>, healthcheck=/health)
CLAUDE.md
.context/...
README.md
.gitignore
```

Chris or Claude Code builds these tarballs during Phase 4 execution. Pseudo-commands to generate them:

```bash
# Static template
mkdir -p /tmp/static-template/{assets,.context/skills}
# ... populate files with <PLACEHOLDER> markers ...
cd /tmp/static-template && tar -czf ../static.tar.gz .
cp /tmp/static.tar.gz <server-root>/skills/new-project/templates/
```

### 5. `skills/app-patch/SKILL.md`

```markdown
---
name: app-patch
description: Modify an existing project to fix a bug or add a feature.
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
max_turns: 60
post_review:
  trigger: always
tags: [projects, maintenance]
---

# App Patch

You are modifying an existing project. The job description specifies which
project and what to do.

## Inputs

- Project slug (either in `payload.project_slug` or parse from description: "fix market-tracker: ...")
- Description of the change

## Procedure

### Step 1 — Orient

```bash
cd projects/<slug>
cat CLAUDE.md
cat .context/CONTEXT.md
tail -50 .context/CHANGELOG.md      # recent changes
ls .context/skills/                 # DEBUG.md, PATTERNS.md, GOTCHAS.md if present
```

Also tail the service logs if it's a running service:
```bash
tail -200 "../../volumes/logs/project.<slug>.err.log"
```

### Step 2 — Investigate

Reproduce the issue if possible. Find the relevant code. DON'T start patching
without understanding.

### Step 3 — Patch

Make the change. Prefer minimal diffs. Keep unrelated refactoring out of
this change.

### Step 4 — Test

Run the project's test command if defined. If not, at least verify:
- Service-type projects: restart and hit the healthcheck
  ```bash
  launchctl kickstart -k gui/$(id -u)/com.assistant.project.<slug>
  sleep 3
  curl -f http://localhost:<port><healthcheck_path>
  ```
- Static projects: visually inspect the affected page (WebFetch to localhost won't work for local-CA'd HTTPS; use Read on the file and reason)

### Step 5 — Commit

Per manifest's `patch_mode` (default `branch`):
- `direct`: `git add -A && git commit -m "<subject>" && git push origin main`
- `branch`: create a branch `patch/<short-slug>-<date>`, commit, push, open PR via `gh pr create`
- `pr`: same as branch but wait for manual merge (don't push the change to production until merged)

### Step 6 — Update project CHANGELOG

Append to `projects/<slug>/.context/CHANGELOG.md` per PROTOCOL.md format.
Commit the CHANGELOG update with the code change (same commit preferred, or
follow-up commit on the same branch).

### Step 7 — Final summary

One paragraph: what was broken, what you changed, how to verify, any caveats.

## Gotchas

- Service restarts take time; the healthcheck may fail for ~5s after
  `launchctl kickstart`. Retry 3x with 2s sleep.
- If the project doesn't have a healthcheck endpoint, add one as part of the patch.
- Never commit secrets. Check with `git diff --cached | grep -iE 'api[_-]?key|token|secret|password'` before push.
- If the change requires a new env var, update `.env.example` AND send instructions in the final summary (you can't DM the actual secret).
```

### 6. `skills/new-skill/SKILL.md`

Meta-skill. Drafts a new SKILL.md from a description, runs code-review on it,
merges (or PRs) into ai-server.

```markdown
---
name: new-skill
description: Author a new skill from a natural-language description.
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 30
post_review:
  trigger: always
tags: [meta, skill-creation]
---

# New Skill

You are creating a new skill: a directory under `skills/<n>/` with a
`SKILL.md` and any support files.

## Inputs

- Description of what the skill should do
- Optional hints in payload: `model`, `effort`, `trigger` (scheduled/ad-hoc/event), `required_tools`

## Procedure

### Step 1 — Analyze the description

Decide:
- **Slug**: 2-3 lowercase words with hyphens. E.g., "crypto-price-alerts".
- **Trigger type**: scheduled (cron), ad-hoc (user-invoked), or event-driven.
- **Inputs**: what does the skill need to be told?
- **Outputs**: what does "success" look like?
- **Tools needed**: minimal set — don't list tools that aren't used.
- **Model/effort**: default Sonnet/medium unless the work is clearly coding-heavy (Opus/high) or trivial (Haiku/low).
- **Escalation rule**: when to retry with stronger config.

If multiple skills already exist with overlapping purpose, STOP and explain
the overlap rather than creating a duplicate.

### Step 2 — Read prior skills as examples

```bash
cat skills/research-report/SKILL.md  # good structure reference
cat skills/chat/SKILL.md             # minimal example
cat .context/SKILLS_REGISTRY.md      # don't duplicate existing skills
cat .context/PROTOCOL.md             # write-back conventions
```

### Step 3 — Draft the SKILL.md

```bash
mkdir -p skills/<slug>
# Write skills/<slug>/SKILL.md with:
#   - YAML frontmatter (schema matches skills/README.md)
#   - # Title
#   - ## When to use
#   - ## Inputs
#   - ## Procedure (numbered steps)
#   - ## Quality gate
#   - ## Gotchas
#   - ## Files this skill updates
```

Tone: imperative, tight. Opus 4.7 rewards explicit instructions; don't hedge.

### Step 4 — Register

Append to `.context/SKILLS_REGISTRY.md` in the "Installed" table.

### Step 5 — (If scheduled) insert a schedule row

Only if the description makes a schedule obvious (e.g., "every morning at 8am"):

```sql
INSERT INTO schedules (name, cron_expression, job_kind, job_description)
VALUES ('<slug>-daily', '0 8 * * *', '<slug>', '<human-readable trigger description>');
```

### Step 6 — Commit

The runner's post-review sub-agent will review the SKILL.md. If LGTM, the
change auto-merges on push (per policy). If CHANGES, iterate. If BLOCKER,
don't push; surface the concern in the summary.

```bash
cd <server-root>
git add skills/<slug>/ .context/SKILLS_REGISTRY.md
git commit -m "Add skill: <slug>"
# Don't push until review passes
```

Wait for the runner to spawn the code-review sub-agent on this commit's
diff; it will set `review_outcome` on this job. If LGTM: `git push`. If
CHANGES: address them, amend the commit, re-push.

### Step 7 — Final summary

Name of the new skill, how to trigger it, any schedule configured, any
manual steps.

## Quality gate

- [ ] YAML frontmatter parses cleanly
- [ ] `required_tools` lists only tools actually referenced in the procedure
- [ ] No overlap with an existing skill
- [ ] SKILLS_REGISTRY.md updated
- [ ] Procedure is numbered and explicit (Opus 4.7 follows instructions literally)
- [ ] Quality gate section exists with measurable checks

## Gotchas

- Don't make the first skill perfect. Most skills improve via
  `review-and-improve` after some runs reveal gotchas.
- If the skill is internal (spawned by runner, not user-triggered), start the
  slug with `_` (like `_writeback`). See `.context/SKILLS_REGISTRY.md`
  "Conventions" section.
```

### 7. MCP servers

**`src/runner/mcp_projects.py`**:

```python
"""
In-process MCP server exposing project-related tools to skills that need them
(self-diagnose, review-and-improve, others).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from src.config import settings
from src.registry.manifest import Manifest, load_all, load as load_one


@tool("list_projects", "Return all registered projects with their manifests")
async def list_projects_tool() -> str:
    manifests = load_all()
    return "\n".join(
        f"- {m.slug}: {m.type} @ {m.subdomain} "
        f"(port={m.port}, healthcheck={m.healthcheck})"
        for m in manifests
    )


@tool("get_project", "Get full manifest for a specific project by slug")
async def get_project_tool(slug: str) -> str:
    path = settings.projects_dir / slug / "manifest.yml"
    if not path.exists():
        return f"No project {slug}"
    return path.read_text()


@tool("read_project_logs", "Return last N lines of a project's stderr log")
async def read_project_logs_tool(slug: str, n: int = 100) -> str:
    log = settings.logs_dir / f"project.{slug}.err.log"
    if not log.exists():
        return f"No logs at {log}"
    result = subprocess.run(
        ["tail", f"-n{n}", str(log)], capture_output=True, text=True, timeout=5
    )
    return result.stdout


@tool("restart_project", "Restart a service-type project via launchctl kickstart")
async def restart_project_tool(slug: str) -> str:
    label = f"com.assistant.project.{slug}"
    result = subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{subprocess.check_output(['id', '-u']).decode().strip()}/{label}"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return f"Restart failed: {result.stderr}"
    return f"Restarted {slug}"


def server():
    return create_sdk_mcp_server(
        name="projects",
        version="0.1.0",
        tools=[list_projects_tool, get_project_tool, read_project_logs_tool, restart_project_tool],
    )
```

**`src/runner/mcp_dispatch.py`**:

```python
"""
In-process MCP server exposing a dispatch tool so a parent skill can enqueue
a child job (fire-and-forget, unlike code-review sub-agent which is sync).

Used by self-diagnose, review-and-improve, server-upkeep.
"""
from claude_agent_sdk import create_sdk_mcp_server, tool

from src.gateway.jobs import enqueue_job


@tool("enqueue_job", "Enqueue a new job by kind + description")
async def enqueue_job_tool(kind: str, description: str, payload: dict | None = None) -> str:
    job = await enqueue_job(
        description, kind=kind, payload=payload, created_by="dispatch-mcp"
    )
    return f"Enqueued: {str(job.id)[:8]} ({kind})"


def server():
    return create_sdk_mcp_server(
        name="dispatch",
        version="0.1.0",
        tools=[enqueue_job_tool],
    )
```

**Wire into `session.py`**:

```python
# In _build_options:
from src.runner.mcp_projects import server as projects_mcp_server
from src.runner.mcp_dispatch import server as dispatch_mcp_server

# Skills that need these tools (declared via tag or required_tools):
NEEDS_PROJECTS_MCP = {"self-diagnose", "review-and-improve", "server-upkeep"}
NEEDS_DISPATCH_MCP = {"self-diagnose", "review-and-improve"}

if skill_cfg and skill_cfg.name in NEEDS_PROJECTS_MCP:
    mcp_servers = kwargs.setdefault("mcp_servers", [])
    mcp_servers.append(projects_mcp_server())
if skill_cfg and skill_cfg.name in NEEDS_DISPATCH_MCP:
    mcp_servers = kwargs.setdefault("mcp_servers", [])
    mcp_servers.append(dispatch_mcp_server())
```

### 8. `skills/self-diagnose/SKILL.md`

```markdown
---
name: self-diagnose
description: Investigate a failure (job, service, or healthcheck) and propose or apply a fix.
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Bash, Glob, Grep]
max_turns: 30
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: xhigh
tags: [meta, recovery, event-triggered]
---

# Self Diagnose

You are investigating a failure. The job's `payload` contains a `target`
field indicating what failed:

- `{target_kind: "job", target_id: "abc12345"}` — a specific failed job
- `{target_kind: "service", slug: "market-tracker"}` — a failing service
- `{target_kind: "skill", skill_name: "research-report"}` — a skill failing repeatedly
- `{target_kind: "freeform", description: "..."}` — user-invoked; parse the description

## Procedure

### Step 1 — Gather evidence

Use the `projects` MCP tools and direct file reads:

- For a specific job: read `volumes/audit_log/<target_id>.jsonl`
- For a service: `read_project_logs(slug, n=300)` and check `last_healthy_at`
- For a skill: query recent failures
  ```bash
  psql assistant -c "SELECT id, description, error_message, created_at FROM jobs
                     WHERE resolved_skill = '<skill>' AND status = 'failed'
                     ORDER BY created_at DESC LIMIT 10;"
  ```

### Step 2 — Identify root cause

Be specific. "The service crashed" is not enough. You need: *what* crashed,
*why*, *when it started*. Cross-reference the audit log with service logs
if they overlap in time.

### Step 3 — Classify risk

- **Very-low-risk**: restart a service, truncate a log file, clear a lock.
- **Low-risk**: adjust a config value (e.g., increase a timeout).
- **Medium-risk**: patch a project's code.
- **High-risk**: patch server code.

### Step 4 — Act based on risk

- **Very-low-risk**: use `projects` MCP `restart_project` or run `bash` commands. Verify the fix. Update CHANGELOG.
- **Low-risk**: make the change, test, commit, update CHANGELOG.
- **Medium-risk**: DON'T patch directly. Use `dispatch` MCP to enqueue an `app-patch` job with a detailed description. Wait for it to complete; report outcome.
- **High-risk**: same but enqueue `server-patch`.

### Step 5 — Record in DEBUG.md

Append to the relevant module's DEBUG.md:
- What symptom you saw
- What you tried that didn't work (brief)
- What did work (the fix)
- A diagnostic shortcut for next time (a specific grep, a specific query)

### Step 6 — Final summary

Root cause + fix + any follow-up action you delegated. One paragraph.

## Gotchas

- Don't restart services repeatedly hoping the issue resolves itself —
  investigate *why* first.
- If you can't determine root cause in 30 turns, STOP, summarize what you
  know, and recommend manual investigation.
- Never try to "fix" by deleting audit logs or DB rows; that destroys
  evidence you'll want later.
- Watch for cascade failures: if market-tracker is failing healthcheck
  because its upstream API is down, the fix is to wait / add a retry, not
  patch market-tracker.
```

### 9. `src/runner/events.py`

Event-triggered rules engine. Subscribes to `jobs:done:*`, evaluates rules.

```python
"""
Event-triggered rules. Subscribes to jobs:done:* and jobs:failed:* channels;
when rules match, enqueues follow-up jobs.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func, and_

from src.db import async_session
from src.gateway.jobs import enqueue_job
from src.models import Job, JobStatus, Project

logger = structlog.get_logger()


async def evaluate_rules() -> None:
    """Evaluate rules. Called every time a job completes or on a timer."""
    await _rule_consecutive_skill_failures()
    await _rule_project_healthcheck_failures()


async def _rule_consecutive_skill_failures() -> None:
    """If a skill has failed >= 2 times in the last 10 minutes, enqueue self-diagnose."""
    since = datetime.now(timezone.utc) - timedelta(minutes=10)
    async with async_session() as s:
        result = await s.execute(
            select(Job.resolved_skill, func.count(Job.id))
            .where(and_(
                Job.status == JobStatus.failed.value,
                Job.created_at > since,
                Job.resolved_skill.isnot(None),
                Job.resolved_skill != "self-diagnose",  # avoid recursion
            ))
            .group_by(Job.resolved_skill)
            .having(func.count(Job.id) >= 2)
        )
        failing_skills = [row[0] for row in result.all()]

    for skill in failing_skills:
        # Did we already enqueue self-diagnose for this skill recently?
        async with async_session() as s:
            recent = await s.execute(
                select(func.count(Job.id)).where(and_(
                    Job.kind == "self-diagnose",
                    Job.created_at > since,
                    Job.description.like(f"%{skill}%"),
                ))
            )
            if recent.scalar() > 0:
                continue
        await enqueue_job(
            f"Skill '{skill}' has failed 2+ times in 10 min. Investigate.",
            kind="self-diagnose",
            payload={"target_kind": "skill", "skill_name": skill},
            created_by="event-trigger",
        )
        logger.info("enqueued self-diagnose for failing skill", skill=skill)


async def _rule_project_healthcheck_failures() -> None:
    """If a project's last_healthy_at is > 20 min ago (4 missed 5-min checks), enqueue self-diagnose."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=20)
    async with async_session() as s:
        result = await s.execute(
            select(Project.slug).where(and_(
                Project.type != "static",
                Project.last_healthy_at < cutoff,
            ))
        )
        unhealthy = [row[0] for row in result.all()]

    for slug in unhealthy:
        async with async_session() as s:
            recent = await s.execute(
                select(func.count(Job.id)).where(and_(
                    Job.kind == "self-diagnose",
                    Job.created_at > datetime.now(timezone.utc) - timedelta(minutes=20),
                    Job.description.like(f"%{slug}%"),
                ))
            )
            if recent.scalar() > 0:
                continue
        await enqueue_job(
            f"Project '{slug}' has been unhealthy for 20+ minutes. Investigate.",
            kind="self-diagnose",
            payload={"target_kind": "service", "slug": slug},
            created_by="event-trigger",
        )
        logger.info("enqueued self-diagnose for unhealthy project", slug=slug)


async def event_loop(shutdown: asyncio.Event) -> None:
    """Run the rules engine every 60 seconds."""
    while not shutdown.is_set():
        try:
            await evaluate_rules()
        except Exception:
            logger.exception("event rules tick failed")
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=60)
            break
        except asyncio.TimeoutError:
            continue
```

### 10. Wire `events.py` into the runner

In `src/runner/main.py`:

```python
from src.runner.events import event_loop

# In main():
tasks = [
    asyncio.create_task(_job_loop(), name="job_loop"),
    asyncio.create_task(_scheduler_loop(), name="scheduler_loop"),
    asyncio.create_task(_cancel_listener(), name="cancel_listener"),
    asyncio.create_task(event_loop(_shutdown), name="event_loop"),  # NEW
]
```

### 11. Tests

Add to `tests/`:

- `test_review_parser.py` — `_parse_outcome` cases
- `test_events.py` — rules fire correctly; don't spam duplicates
- `test_mcp_tools.py` — basic invocations (requires live DB; may need to be integration tests)

Run before every commit:
```bash
pipenv run pytest tests/ -v
```

---

## Runbook

### Step 1 — Build `review.py` + code-review skill

Create the two files, write tests, integrate into `_process_job`. Commit:
```
feat(review): add code-review sub-agent on code-touching jobs
```

**Checkpoint**: `/task --effort=high write me a Python function that reverses a string` → routes to `app-patch`, runs, triggers code-review sub-agent. Check `jobs.review_outcome` populated.

### Step 2 — Build new-project skill + templates

Create `skills/new-project/SKILL.md`. Build `templates/static.tar.gz` and `templates/fastapi-service.tar.gz` by scaffolding a minimal example of each. Commit:
```
feat(skills): add new-project skill with static + fastapi templates
```

**Checkpoint**: `/task new project: simple HTTP uptime monitor for my other projects` → scaffolds, commits, pushes, registers, returns URL.

### Step 3 — Build app-patch skill

Create `skills/app-patch/SKILL.md`. Test against one of the previously-created projects.
Commit.

**Checkpoint**: `/task fix bingo: add dark mode toggle` → patches the bingo project, reviews the diff, commits.

### Step 4 — Build new-skill skill

Create `skills/new-skill/SKILL.md`. Test by having it create a trivial skill (e.g., `echo` that just echoes back its input).
Commit.

**Checkpoint**: `/task new skill: tell me a joke when I say "joke time"`. See a new skill directory, SKILL.md, registry update, commit, auto-push after LGTM.

### Step 5 — Build MCP servers

Create `src/runner/mcp_projects.py`, `src/runner/mcp_dispatch.py`. Wire into `session.py`.
Commit.

**Checkpoint**: the next skill that needs them (self-diagnose) can list projects, read logs.

### Step 6 — Build self-diagnose skill

Create `skills/self-diagnose/SKILL.md`.
Commit.

**Checkpoint**: manually kill the market-tracker service (`launchctl unload <its-plist>`). Within ~20 min, `healthcheck-all` detects failure, `events.py` fires, self-diagnose runs, investigates, either restarts it or delegates to `app-patch`.

### Step 7 — Build event trigger loop

Create `src/runner/events.py`. Wire into `main.py`.
Commit.

**Checkpoint**: simulate failures (submit bad tasks that fail twice); verify self-diagnose auto-enqueued.

### Step 8 — Final sweep

Update `.context/SYSTEM.md`, `.context/SKILLS_REGISTRY.md`, `.context/modules/runner/CHANGELOG.md`, `MISSION.md` (Phase 4 → shipped).

Commit: `Phase 4: expansion skills (new-project, app-patch, new-skill, self-diagnose, code-review) + MCP servers + event triggers`.

Push.

---

## Rollback

If any skill misbehaves, disable it by adding a `.disabled` suffix to its directory:
```bash
mv skills/<skill-name> skills/<skill-name>.disabled
```

The runner will fall through to "no skill found" and run a generic session. No code change needed.

To disable event triggers:
```python
# Comment out the event_loop task in main.py and restart runner
```

To disable post-review:
```python
# Set POST_REVIEW_KINDS = {} in main.py
```

---

## NOT in Phase 4

- **`server-upkeep`, `backup`, `server-patch`, `review-and-improve`**: Phase 5.
- **`research-deep`, `idea-generation`, `project-update-poll`, `restore`**: Phase 6.
- **Cross-skill state sharing** (e.g., self-diagnose remembers prior diagnoses of the same issue): skip for now. If it becomes necessary, store in audit_log summaries and have skills read them.
- **Rate limiting on event-triggered jobs**: current rules dedupe (won't fire if a self-diagnose for same target already pending), but under pathological conditions could loop. Phase 5 adds a hard cap.

---

## After Phase 4

Phase 5: operations — making the system self-maintaining. See `docs/PHASE_5_PLAN.md`.
