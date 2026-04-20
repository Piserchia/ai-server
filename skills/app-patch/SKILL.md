---
name: app-patch
description: Patch an existing project to fix bugs or add features
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
post_review:
  trigger: always
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: xhigh
tags: [projects, maintenance]
---

# App Patch

You are patching an existing project to fix a bug or add a feature. The project
lives at `projects/<slug>/` and is its own git repo (separate from the
ai-server repo).

## Multi-turn task protocol

This skill runs inside a multi-turn task. The user interacts via a Telegram
thread. You communicate back to them through audit log events:

- **To ask the user a question** (open-ended): emit a `task_question` event
  and complete normally. The system will DM them your question and wait for
  their reply. A new job will start with their answer in context.

  ```python
  # In your final text, just state what you found and what you need to know.
  # Then emit the event:
  audit_log.append(job_id, "task_question",
      question="Which login form should I fix — the admin one at /admin/login or the user one at /login?")
  ```

- **To offer structured choices**: emit a `task_choices` event. The system
  will show inline buttons in Telegram.

  ```python
  audit_log.append(job_id, "task_choices",
      question="Which login form?",
      options=["Admin (/admin/login)", "User (/login)", "Both"])
  ```

- **To signal you're done** (code committed and deployed): emit `task_complete`.
  The system will ask the user for approval.

  ```python
  audit_log.append(job_id, "task_complete",
      summary="Fixed the admin login: changed auth.py line 42. Verified via healthcheck.")
  ```

**IMPORTANT**: Do NOT emit `task_complete` unless you have actually committed
and pushed code. If you only analyzed the codebase or produced a plan, your
final text is your response — the system will show it to the user and they
can reply in the thread to continue.

## Inputs you will receive

Extract the project slug from the job description. Common patterns:

- "fix market-tracker: crypto dashboard shows NaN" → slug is `market-tracker`
- "update baseball-bingo app to add login" → slug is `baseball-bingo`
- Or look for `payload.project_slug` if set in the job payload.

If this is a **continuation job** (part of a multi-turn task), the system
prompt will include a "Task conversation" section with prior turns. Read it
to understand what was already discussed and what the user wants next.

## Protocol

Follow `.context/PROJECT_PROTOCOL.md` (in the ai-server root) for the
write-back protocol.

## Procedure

### Step 1: Orient

Read the project's context files:
- `projects/<slug>/CLAUDE.md`
- `projects/<slug>/.context/CONTEXT.md`
- `projects/<slug>/.context/CHANGELOG.md` (last 3 entries only)
- `projects/<slug>/skills/GOTCHAS.md`

If the project directory does not exist, stop and report it.

### Step 2: Triage — is this a quick fix or a major feature?

Assess the request against the codebase:

**Quick fix** (do it now): bug fix, config change, small UI tweak, adding
a field, fixing a typo. Criteria: touches <5 files, no new architecture,
no new dependencies, can be done in this session.

**Medium feature** (plan first, then implement): new page, new API endpoint,
adding a library, moderate refactor. Criteria: touches 5-15 files, clear
approach, one session of planning + one of implementation.

**Major feature** (plan, get approval, implement in phases): new subsystem,
new backend, auth system, multiplayer, database schema changes. Criteria:
touches 15+ files, needs architecture decisions, multiple sessions.

For **quick fixes**: proceed directly to Step 4 (Patch).

For **medium features**: produce a plan in your response describing what
you'll change, which files, and what the approach is. End your turn — the
user will reply to approve or adjust. On the next turn, implement.

For **major features**: produce a high-level architecture analysis:
- What exists today (tech stack, key modules, current limitations)
- What needs to change (new components, data flow, dependencies)
- A phased approach (what to build first, second, third)
- What you need from the user (design decisions, priorities)

Then emit `task_question` asking which phase to start with, or asking the
design question that blocks progress. Do NOT attempt to implement a major
feature in one turn.

### Step 3: Plan (medium/major features only)

If this is a continuation after the user approved your plan:
1. Confirm which phase or part you're implementing
2. List the specific files you'll create or modify
3. Proceed to Step 4

### Step 4: Patch

Make changes. Follow these principles:
- Prefer editing existing files over creating new ones
- Change only what is necessary for this phase
- Preserve the project's existing code style and conventions
- If you need to add a dependency, note it explicitly

### Step 5: Test

- For service-type projects: restart via `launchctl kickstart -k gui/$(id -u)/com.assistant.project.<slug>`, wait 3 seconds, then hit the healthcheck endpoint from `manifest.yml`.
- For multi-service projects: check `manifest.yml` for `services` array. Restart and healthcheck each.
- For static projects: verify file contents by reading back the changed files.
- If the project has a `test_command` in `manifest.yml`, run it.

### Step 6: Check for secrets

```bash
cd projects/<slug>
git diff --cached | grep -iE 'api[_-]?key|token|secret|password'
git diff | grep -iE 'api[_-]?key|token|secret|password'
```

If real credentials found, abort the commit.

### Step 7: Commit and push

```bash
cd projects/<slug>
git add -A
git commit -m "<concise subject describing the change>"
git push origin main
```

### Step 8: Update docs

Append to `projects/<slug>/.context/CHANGELOG.md`:
```
## YYYY-MM-DD — <short description>

**What changed**: <list of files and modifications>
**Why**: <reasoning>
**How to verify**: <one sentence>
```

### Step 9: Signal completion

After code is committed and pushed, emit `task_complete`:

```python
audit_log.append(job_id, "task_complete",
    summary="<one paragraph: what changed, how to verify>")
```

Your final text message should be the same summary. This becomes the
Telegram DM the user receives.

## Quality gate

Before emitting `task_complete`:

- [ ] Changes are minimal and targeted for this phase
- [ ] No secrets in the diff
- [ ] Service restarts and passes healthcheck (if applicable)
- [ ] `projects/<slug>/.context/CHANGELOG.md` updated
- [ ] Changes committed and pushed to `origin main`
- [ ] `task_complete` event emitted with summary

If you only analyzed or planned (no code committed), do NOT run this gate
or emit `task_complete`. Just end your turn with your analysis/plan as text.

## Gotchas (living section — append when you learn something)

- **Separate git repo.** `projects/<slug>/` is its OWN git repo. Always `cd`
  into it before git operations. Never run `git` from ai-server root.
- **launchctl label format.** `gui/$(id -u)/com.assistant.project.<slug>`.
- **Multi-service projects.** Check `manifest.yml` for `services` array.
  Each sub-service: `com.assistant.project.<slug>-<service-name>`.
- **Healthcheck path.** Read from `manifest.yml` `healthcheck` field.
- **Push failures.** `git pull --rebase origin main` then retry. No force push.
- **Major features need multiple turns.** Don't try to build auth + multiplayer
  + UI in one session. Plan first, get approval, implement in phases.
