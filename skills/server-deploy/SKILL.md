---
name: server-deploy
description: Deploy the ai-server itself — ff-only pull into the production checkout, migrate, test-gate, restart the three processes. The server-side twin of atlas-redeploy. Red tests mean the old code keeps running.
model: claude-sonnet-4-6
effort: low
permission_mode: bypassPermissions
required_tools: [Read, Bash, Glob, Grep]
max_turns: 30
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
tags: [operations, deploy, server]
---

# Server Deploy

Deterministic deploy pipeline for the ai-server itself. Triggered via
`/task deploy server` (or "deploy the server") after commits land on
`origin/main` from the dev repo (`~/Documents/repos/ai-server`).

The production checkout at `~/Library/Application Support/ai-server` is a
**pull-only deploy target** (single-writer rule, CLAUDE.md): code is born in
the dev repo; only runtime doc learnings are born here (and they leave via
`scripts/sync-learnings.sh`, not via commits on main).

## Procedure

All from `SRV="$HOME/Library/Application Support/ai-server"`.

### 0. Publish pending learnings FIRST

```bash
cd "$SRV"
bash scripts/sync-learnings.sh   # pushes runtime doc drift to origin/runtime-learnings
```

This must run before the pull so no runtime-written docs can be lost.

### 1. Reconcile doc drift, then pull

```bash
cd "$SRV"
BEFORE=$(git rev-parse --short HEAD)
git stash push --include-untracked=no -m "server-deploy doc drift $(date -u +%F)" \
  -- .context docs/Troubleshooting.md skills 2>/dev/null || true
git pull --ff-only
AFTER=$(git rev-parse --short HEAD)
git stash pop 2>/dev/null || true   # conflict → see rule below
git log --oneline "$BEFORE..$AFTER"
```

- `BEFORE == AFTER` → report "already up to date" and stop.
- **Pull refuses (divergence)**: STOP. Never reset/force. Report
  `git status --short`, `git log --oneline origin/main..HEAD` (runtime-only
  commits = process violation — name them), and `HEAD..origin/main`.
- **Stash pop conflicts**: the incoming main already contains a merged
  version of the drifted docs. Resolve by KEEPING the incoming (main)
  version: `git checkout --theirs` is not applicable to stash pops — instead
  `git checkout -- <conflicted file>` and `git stash drop`. The runtime
  copy was already published to `runtime-learnings` in step 0, so nothing
  is lost. Note it in the summary.

### 2. Dependencies + migrations

```bash
cd "$SRV"
if git diff --name-only "$BEFORE..$AFTER" | grep -q '^Pipfile'; then
  pipenv install --deploy
fi
pipenv run alembic upgrade head    # idempotent
```

### 3. Test gate (the deploy gate)

```bash
cd "$SRV" && pipenv run pytest -q
```

**Any failure → STOP. Do not restart anything.** Summary = failing output +
commit range, so the fix lands in the dev repo first. Red tests never reach
the running services.

### 4. Restart — bot and web directly, runner DETACHED

You are running **inside** the runner. `launchctl kickstart -k` on
`com.assistant.runner` from this session kills your own session mid-job
(exit 143 — see app-patch gotcha). The runner restart must therefore be
**detached and delayed** so this job can finish recording itself first:

```bash
UID_N=$(id -u)
launchctl kickstart -k gui/$UID_N/com.assistant.web
launchctl kickstart -k gui/$UID_N/com.assistant.bot
sleep 3
curl -so /dev/null -w '%{http_code}' --max-time 5 http://localhost:8080/health  # expect 200

# Detached runner restart, 20s after this session ends:
nohup /bin/bash -c "sleep 20 && launchctl kickstart -k gui/$UID_N/com.assistant.runner" \
  >/dev/null 2>&1 &
```

### 5. Summary (final text — write it BEFORE the runner restart fires)

One paragraph: BEFORE→AFTER commits deployed, gate results, web/bot restart +
health code, and the line **"runner restart is scheduled detached in ~20s;
verify with `/status` in a minute or check /health freshness"**. The external
heartbeat worker alerts if the runner fails to come back.

If working inside a task, emit `task_complete` with that summary.

## Hard rules

- `--ff-only` always. Divergence is a human decision — report, never resolve.
- Red tests never reach production. No exceptions.
- NEVER `launchctl kickstart` the runner synchronously from this session —
  detached + delayed only (step 4).
- Never edit code files in the production checkout. Doc drift is handled by
  step 0/1, code belongs in `~/Documents/repos/ai-server`.
- **Global-protocol exemption**: do NOT write CHANGELOG entries in the
  production checkout — changelog entries for the deploy live in the DEV
  repo. Runtime GOTCHAS you discover during a deploy ARE allowed (they're
  what sync-learnings exists for).

## Gotchas

- **The runner restart races job completion.** The 20s nohup delay exists so
  `_finish_job` + notifications complete before SIGTERM. If deploy summaries
  ever stop arriving, suspect this window first.
- **Stash pop after pull**: only doc paths are stashed; a conflict means main
  already merged those learnings — keep main's version (step 1), never hand-merge
  in prod.
- **pipenv in launchd context**: the plists invoke the venv python directly;
  after `pipenv install --deploy` no plist changes are needed unless the venv
  path changed (it shouldn't — report if `pipenv --venv` moved).
