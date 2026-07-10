---
name: atlas-redeploy
description: Pull, verify, migrate, build, and restart the Atlas project (projects/atlas) — the standard deploy path after any commit to the Atlas dev repo. Refuses to restart services if tests fail.
model: claude-sonnet-4-6
effort: low
permission_mode: bypassPermissions
required_tools: [Read, Bash, Glob, Grep]
max_turns: 30
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
tags: [atlas, operations, deploy]
---

# Atlas Redeploy

Deterministic deploy pipeline for the Atlas project. Triggered via `/task redeploy atlas`
(or the job API) after commits land in `~/Documents/repos/atlas`. The gate rule is absolute:
**a red test suite means services keep running the old code** — report the failures instead.

## Procedure

All from `ATLAS="$HOME/Library/Application Support/ai-server/projects/atlas"`.

### 1. Pull + report the delta

```bash
cd "$ATLAS"
BEFORE=$(git rev-parse --short HEAD)
git pull --ff-only    # ff-only: a non-ff means the runtime clone diverged — STOP and report
AFTER=$(git rev-parse --short HEAD)
git log --oneline "$BEFORE..$AFTER"
```

If `BEFORE == AFTER`: report "already up to date" and stop (nothing to deploy). Never
`git reset`/`checkout --force`; a dirty tree or divergence is a finding, not an obstacle.

**If the pull refuses (divergence or dirty tree), the report MUST include the evidence**
so the human can decide in one round-trip:

```bash
git status --short
git remote -v
git fetch origin && git log --oneline origin/master..HEAD   # commits only the runtime has
git log --oneline HEAD..origin/master                        # commits only the dev repo has
```

Include the standard resolution in the report (human runs it, not this skill):
backup branch (`git branch backup-<date>`) → verify origin points at
`~/Documents/repos/atlas` → `reset --hard` to the last common commit → redeploy.
Root-cause context: commits must only ever be born in the dev repo (single-writer rule,
atlas CLAUDE.md §Deployment topology); runtime-only commits are a process violation —
name the offending commits and their author identity in the summary.

### 2. Environment + migrations

```bash
set -a; source .env; set +a
dbmate --migrations-dir db/migrations up      # idempotent; applies anything new
```

### 3. Dependencies + test gates (the deploy gate)

Only reinstall when inputs changed between BEFORE..AFTER (check `git diff --name-only`):
- `dashboard/pyproject.toml` changed → `dashboard/.venv/bin/pip install -e "./dashboard[dev,feeds]" -q`
- `pmedge/pyproject.toml` changed → same pattern for pmedge
- `web/package-lock.json` changed → `cd web && npm ci`

Always run the gates:

```bash
cd "$ATLAS/dashboard" && .venv/bin/python -m pytest -q     # must be green
cd "$ATLAS/pmedge" && .venv/bin/python -m pytest -q        # must be green
```

**Any failure → STOP. Do not build, do not restart.** Summary = the failing output + the
commit range, so the fix lands in the dev repo first.

### 4. Build web (only if web/ changed in the range)

```bash
cd "$ATLAS/web" && npm run build    # a build failure also stops the deploy
```

### 5. Restart + verify

Restart only what the change range touches (web/ → atlas; dashboard/ → atlas-dash-scheduler;
pmedge/ → atlas-pm-edge; when unsure, all three):

```bash
UID_N=$(id -u)
launchctl kickstart -k gui/$UID_N/com.assistant.project.atlas
launchctl kickstart -k gui/$UID_N/com.assistant.project.atlas-dash-scheduler
launchctl kickstart -k gui/$UID_N/com.assistant.project.atlas-pm-edge
sleep 5
bash "$ATLAS/scripts/atlas-status.sh"
curl -so /dev/null -w '%{http_code}' --max-time 5 http://localhost:8791/   # expect 200
```

Any service NOT RUNNING or a non-200 → tail its err log
(`~/Library/Application Support/ai-server/volumes/logs/project.atlas*.err.log`), include the
tail in the summary, and flag the deploy DEGRADED.

### 6. Summary

One paragraph: BEFORE→AFTER commits deployed, gates run + results, services restarted,
healthcheck code. If stopped at a gate: what failed and where to look.

## Hard rules

- Never edit `.env` or any file in the runtime clone — deploys are read-only except for
  build artifacts. Code changes belong in `~/Documents/repos/atlas`.
- `--ff-only` always. Divergence between dev repo and runtime clone is a human decision.
- Red tests never reach production. No exceptions, including "it's just a docs change"
  (docs-only ranges will pass the gates anyway, so run them).
