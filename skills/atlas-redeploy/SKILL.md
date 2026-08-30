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
context_files: ["skills/atlas-redeploy/GOTCHAS.md", ".context/SYSTEM.md"]
---

# Atlas Redeploy

Deterministic deploy pipeline for the Atlas project. Triggered via `/task redeploy atlas`
(or the job API) after commits land on `origin/master` — GitHub `Piserchia/atlas`, the
canonical repo since 2026-07-31, pushed from any development machine. The gate rule is
absolute: **a red test suite means services keep running the old code** — report the
failures instead.

## Procedure

All from `ATLAS="$HOME/Library/Application Support/ai-server/projects/atlas"`.

### 1. Pull + report the delta

```bash
cd "$ATLAS"
STATE_DIR="$HOME/Library/Application Support/ai-server/volumes/state"
MARKER="$STATE_DIR/deployed-sha-atlas"
BEFORE=$(git rev-parse --short HEAD)
git pull --ff-only    # ff-only: a non-ff means the runtime clone diverged — STOP and report
AFTER=$(git rev-parse --short HEAD)
# First use: seed the marker from BEFORE — the pre-pull state IS the last
# deployed state, so red-gated runs before the first green one can't
# re-strand their ranges behind a later run's BEFORE (review catch
# 2026-08-18: red run, then green run, both markerless, would have
# reproduced the incident and made it permanent).
[ -s "$MARKER" ] || { mkdir -p "$STATE_DIR"; git rev-parse "$BEFORE" > "$MARKER"; }
# Range base = the last SUCCESSFULLY deployed SHA, not this pull's start point.
# A gate-failed deploy advances the clone without shipping, so BEFORE..AFTER
# would silently drop that run's paths from every later check (2026-08-17
# incident: web/ was pulled by a red-gated run; the next deploy's range had no
# web/ so the build was skipped — stale bundle behind a green healthcheck).
RANGE_BASE=$BEFORE
if [ -s "$MARKER" ] && git merge-base --is-ancestor "$(cat "$MARKER")" "$AFTER" 2>/dev/null; then
  RANGE_BASE=$(cat "$MARKER")
fi
git log --oneline "$RANGE_BASE..$AFTER"
```

If the undeployed range is empty (`git rev-parse "$RANGE_BASE"` equals
`git rev-parse "$AFTER"`): report "already deployed" and stop. `BEFORE == AFTER`
alone is NOT a reason to stop — when the marker lags the clone, a previous run
pulled these commits but never shipped them, and this deploy proceeds over
`RANGE_BASE..AFTER` (that no-op-pull recovery is the point of the marker).
The marker always exists past the seed line above, and a failed run never
moves it — so consecutive red runs accumulate into one honest range. Never `git reset`/`checkout --force`; a dirty tree or
divergence is a finding, not an obstacle.

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
`https://github.com/Piserchia/atlas.git` → `reset --hard` to the last common commit →
redeploy. Root-cause context: commits reach production only via GitHub `origin/master`
(GitHub-canonical rule, atlas CLAUDE.md §Deployment topology); runtime-only commits are
a process violation — name the offending commits and their author identity in the summary.

### 2. Environment + migrations

```bash
set -a; source .env; set +a
dbmate --migrations-dir db/migrations up      # idempotent; applies anything new
```

### 3. Dependencies + test gates (the deploy gate)

Only reinstall when inputs changed in the undeployed range (check
`git diff --name-only "$RANGE_BASE..$AFTER"`):
- `dashboard/pyproject.toml` changed → `dashboard/.venv/bin/pip install -e "./dashboard[dev,feeds]" -q`
- `pmedge/pyproject.toml` changed → same pattern for pmedge
- `web/package-lock.json` changed → `cd web && npm ci`

Always run the gates:

```bash
cd "$ATLAS/dashboard" && .venv/bin/python -m pytest -q     # must be green
cd "$ATLAS/pmedge" && .venv/bin/python -m pytest -q        # must be green
```

Momentum gate — DETERMINISTIC path check, same pattern as the web build
(added 2026-08-07 with the momentum vertical; manifest.yml declares this
gate but this skill is the executor, so it must live here too):

```bash
if git -C "$ATLAS" diff --name-only "$RANGE_BASE..$AFTER" | grep -q '^momentum/'; then
  cd "$ATLAS/momentum" || exit 1
  if [ ! -x .venv/bin/python ]; then    # self-heal: venv is an allowed runtime-clone write
    python3.12 -m venv .venv && .venv/bin/pip install -q -e '.[dev]'
  fi
  .venv/bin/python -m pytest -q         # must be green
else
  echo "no momentum/ changes in range — momentum gate skipped"
fi
```

Trader gate — same deterministic pattern (added 2026-08-26 with the trader
vertical; manifest.yml declares it, this skill executes it):

```bash
if git -C "$ATLAS" diff --name-only "$RANGE_BASE..$AFTER" | grep -q '^trader/'; then
  cd "$ATLAS/trader" || exit 1
  if [ ! -x .venv/bin/python ]; then    # self-heal: venv is an allowed runtime-clone write
    python3.12 -m venv .venv && .venv/bin/pip install -q -e '.[dev]'
  fi
  .venv/bin/python -m pytest -q         # must be green
else
  echo "no trader/ changes in range — trader gate skipped"
fi
```

Advisors gate — same deterministic pattern (added 2026-08-30 with the
advisors vertical; manifest.yml declares it, this skill executes it):

```bash
if git -C "$ATLAS" diff --name-only "$RANGE_BASE..$AFTER" | grep -q '^advisors/'; then
  cd "$ATLAS/advisors" || exit 1
  if [ ! -x .venv/bin/python ]; then    # self-heal: venv is an allowed runtime-clone write
    python3 -m venv .venv && .venv/bin/pip install -q pytest pyyaml yt-dlp
  fi
  .venv/bin/python -m pytest -q         # must be green
else
  echo "no advisors/ changes in range — advisors gate skipped"
fi
```

**Any failure → STOP. Do not build, do not restart.** Summary = the failing output + the
commit range, so the fix lands in the dev repo first.

### 4. Build web — DETERMINISTIC check, not judgment

```bash
if git -C "$ATLAS" diff --name-only "$RANGE_BASE..$AFTER" | grep -q '^web/'; then
  cd "$ATLAS/web" && npm run build    # a build failure also stops the deploy
else
  echo "no web/ changes in range — build skipped"
fi
```

Run the grep EXACTLY as written and paste its outcome in the summary. Skipping a
needed build ships a stale UI with a green healthcheck (incident 2026-07-10: the
/indicators page deployed code-wise but the old bundle kept serving).

### 5. Restart + verify

Restart only what `RANGE_BASE..AFTER` touches (web/ → atlas; dashboard/ →
atlas-dash-scheduler; pmedge/ → atlas-pm-edge; when unsure, all three):

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

Only when every gate ran green, every restarted service is RUNNING, and the
healthcheck returned 200, advance the deployed marker — a failed or DEGRADED
deploy leaves it untouched so the next run re-covers the same range
(re-running gates/builds over an already-shipped range is idempotent and
cheap; silently skipping an unshipped one is the incident):

```bash
mkdir -p "$STATE_DIR"
git rev-parse HEAD > "$MARKER"
```

### 6. Summary

One paragraph: RANGE_BASE→AFTER commits deployed (note when the base came from
the marker rather than this pull's BEFORE — that means a prior run's undeployed
work shipped now), gates run + results, services restarted, healthcheck code,
and whether the marker advanced. If stopped at a gate: what failed and where
to look.

## Hard rules

- Never edit `.env` or any file in the runtime clone — deploys are read-only except for
  build artifacts. Code changes are born in a development clone (Mini:
  `~/Documents/repos/atlas`, or any laptop clone) and reach here only via GitHub `master`.
- `--ff-only` always. Divergence between dev repo and runtime clone is a human decision.
- Red tests never reach production. No exceptions, including "it's just a docs change"
  (docs-only ranges will pass the gates anyway, so run them).

**Global-protocol exemption**: do NOT update `CHANGELOG.md` (or any tracked file)
inside `projects/atlas` — it is a pull-only clone (single-writer rule) and any tracked
edit blocks every future deploy. Changelog entries for atlas belong in the DEV repo.

## Gotchas

- **Three launchd services, not one**: `com.assistant.project.atlas` (Next.js web),
  `com.assistant.project.atlas-dash-scheduler` (Python scheduler), and
  `com.assistant.project.atlas-pm-edge` (PM-Edge scanner). Restart only what changed;
  when unsure restart all three.
- **Logs are in the server log dir**, not the project: check
  `~/Library/Application Support/ai-server/volumes/logs/project.atlas*.err.log` for
  crash output after a restart.
- **Build is deterministic, not judgment** (step 4): run the exact `grep '^web/'` check on
  the range; skipping a needed build ships a stale UI (incident 2026-07-10).
- **A gate-failed deploy consumes the pull, not the marker** (2026-08-17): the
  clone advances even when the gates go red, so path checks anchored on the
  current pull would miss the failed run's changes forever after. That is why
  every range in this skill is `RANGE_BASE..AFTER` (marker-anchored) and the
  marker only moves on a fully green deploy. A no-op pull with a lagging
  marker is a real deploy, not "already up to date".
- **Runtime-born commits block deploys**: any `git commit` made inside `projects/atlas`
  (instead of a development clone that pushes to GitHub) will cause the next `--ff-only`
  pull to refuse — a process violation; do NOT force-push or reset — stop, report, let the
  human resolve (see `docs/TROUBLESHOOTING.md` § "atlas redeploy reports diverged").
