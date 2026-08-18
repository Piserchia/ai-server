---
name: project-redeploy
description: Deploy any project from its manifest delivery contract — ff-only pull into the runtime clone, run the declared gates (tests/build/healthcheck), restart only the affected services. Red gate = old code keeps running. The generic engine atlas-redeploy is a special case of.
model: claude-sonnet-4-6
effort: low
permission_mode: bypassPermissions
required_tools: [Read, Bash, Glob, Grep]
max_turns: 30
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
tags: [operations, deploy, per-project]
isolation: none
---

# Project Redeploy

The **contract-driven** deploy pipeline for any project. You read the project's
`manifest.yml` `delivery.deploy` block and execute exactly what it declares —
gates in order, path-gated builds, restart only the affected services. The gate
rule is absolute: **a red gate means the services keep running the old code** —
report the failure instead of shipping.

You run AFTER the runner's deploy-authority gate has already confirmed this
project is deployable and this trigger is permitted (delivery contract, Phase
B). You do NOT re-check authority; you execute the deploy safely.

## Inputs

- **project_slug** — from `payload.project_slug`, or parse it from the
  description. The slug is the **directory name under `projects/`**, which can
  differ from the subdomain (e.g. "redeploy the bingo app" → the slug is
  `baseball-bingo`, not `bingo`; "deploy market-tracker" → `market-tracker`).
  Confirm `projects/<slug>/` exists. If you cannot determine a valid slug, stop
  and report it.

Your working directory is already the project's **runtime clone**
(`projects/<slug>/`) — the runner scopes deploy jobs there. Deploys are
read-only on tracked source: the only writes are `git pull`, migrations, build
artifacts, and service restarts. **Never commit, edit tracked files, or
`git reset` here** — for a `dev-repo` topology project the runtime clone is
pull-only and code changes belong in the dev repo (a tracked-file commit here
blocks every future ff-only pull — incident 2026-07-09).

## Procedure

Let `P="$(pwd)"` (the runtime clone). Read `"$P/manifest.yml"` first and hold
its `delivery.deploy` block: `gates` (ordered), `services`, `migrate`, `branch`.

### 0. Verify the delivery contract — FAIL CLOSED

Before touching anything, confirm this project has a real deploy contract:

- If `manifest.yml` has **no `delivery.deploy` block**, STOP and report:
  "`<slug>` has not been migrated to the delivery contract — I won't guess how
  to deploy it. Deploy it via its existing path instead (an in-place project
  deploys through `app-patch`'s inline restart; atlas via `atlas-redeploy`), or
  add a `delivery` block to its manifest."
- If the project is `type: service`/`api` and `delivery.deploy.services` is
  **empty**, STOP and report the same — a pull with no service restart ships
  stale code behind a green healthcheck (the exact failure this skill exists to
  prevent). Do **not** proceed with a bare pull.

Only continue past this step when the contract tells you what to restart.

### 1. Pull + report the delta

```bash
cd "$P"
STATE_DIR="$HOME/Library/Application Support/ai-server/volumes/state"
MARKER="$STATE_DIR/deployed-sha-<slug>"
BEFORE=$(git rev-parse --short HEAD)
git pull --ff-only          # ff-only: a non-ff means the clone diverged — STOP, report
AFTER=$(git rev-parse --short HEAD)
# First use: seed the marker from BEFORE — the pre-pull state IS the last
# deployed state, so red-gated runs before the first green one can't
# re-strand their ranges behind a later run's BEFORE (review catch 2026-08-18).
[ -s "$MARKER" ] || { mkdir -p "$STATE_DIR"; git rev-parse "$BEFORE" > "$MARKER"; }
# Range base = the last SUCCESSFULLY deployed SHA (marker), not this pull's
# start point: a gate-failed deploy advances the clone without shipping, and
# BEFORE..AFTER would silently drop that run's paths from the dep/build/restart
# checks (atlas incident 2026-08-17 — stale bundle behind a green healthcheck).
RANGE_BASE=$BEFORE
if [ -s "$MARKER" ] && git merge-base --is-ancestor "$(cat "$MARKER")" "$AFTER" 2>/dev/null; then
  RANGE_BASE=$(cat "$MARKER")
fi
git log --oneline "$RANGE_BASE..$AFTER"
```

If the undeployed range is empty (`git rev-parse "$RANGE_BASE"` equals
`git rev-parse "$AFTER"`): report "already deployed" and stop. `BEFORE == AFTER`
alone is NOT a reason to stop — a lagging marker means a previous run pulled
commits but never shipped them, and this deploy proceeds over
`RANGE_BASE..AFTER`. The marker always exists past the seed line above, and a
failed run never moves it — consecutive red runs accumulate into one range. If the pull refuses
(divergence or a dirty tree), that is a **finding, not an obstacle** — never
`git reset`/`checkout --force`. Include the evidence so a human can resolve in
one round-trip:

```bash
git status --short
git remote -v
git fetch origin && git log --oneline HEAD..@{u}   # commits only the remote has
git log --oneline @{u}..HEAD                        # commits only the clone has (a violation)
```

### 2. Migrate (if declared)

If `delivery.deploy.migrate` is set, run it (it must be idempotent):

```bash
set -a; [ -f .env ] && source .env; set +a
<the migrate command from the manifest>
```

### 2b. Install dependencies (only when their manifest changed)

A pulled change may add a dependency; a build/test gate that runs without it
red-gates with no way to self-heal. Reinstall ONLY when a dependency file
changed in `RANGE_BASE..AFTER` (read the project's `start_command`/build gate to
find the right interpreter/venv — projects vary):

```bash
CHANGED=$(git diff --name-only "$RANGE_BASE..$AFTER")
# Node (front-end): a changed lockfile → clean install in the web dir.
echo "$CHANGED" | grep -qE '(^|/)package(-lock)?\.json$' && (cd "<web dir from manifest>" && npm ci)
# Python: a changed dep manifest → install into the project's OWN venv
# (find it in start_command, e.g. .venv/bin/python or a pipenv venv). NEVER the
# server's venv.
echo "$CHANGED" | grep -qE '(pyproject\.toml|requirements.*\.txt|Pipfile)' && \
  echo "python deps changed — install into the project venv named in start_command"
```

If nothing dependency-related changed, skip and say so. First-ever deploy of a
freshly-cloned runtime clone counts as "changed" — install + build once.

### 3. Run the gates — in declared order, red = STOP

For each entry in `delivery.deploy.gates`, in order:

- **`kind: test`** — run its `cmd`. Non-zero exit → **STOP the deploy**, do not
  build, do not restart. Summary = the failing output + the
  `RANGE_BASE..AFTER` range, so the fix lands upstream first. The marker does
  not move — the next deploy re-covers this same range.
- **`kind: build`** — if it has `when_paths`, run the build **only if** one of
  those paths changed in range; otherwise skip it and say so:
  ```bash
  if git diff --name-only "$RANGE_BASE..$AFTER" | grep -qE '^(web/|frontend/)'; then
    <build cmd>       # a build failure also STOPS the deploy
  else
    echo "no matching paths changed in range — build skipped"
  fi
  ```
  Run the grep exactly against the manifest's `when_paths` and paste the
  outcome. Skipping a needed build ships a stale bundle behind a green
  healthcheck (incident 2026-07-10).
- **`kind: healthcheck`** — deferred to step 5 (after restart).
- **`kind: command`** — run its `cmd`; non-zero → STOP.

### 4. Restart — only the affected services

Restart only services whose inputs changed in `RANGE_BASE..AFTER` when you can tell;
when unsure, restart all of `delivery.deploy.services`. Labels are
`gui/$(id -u)/com.assistant.project.<service>`:

```bash
UID_N=$(id -u)
launchctl kickstart -k gui/$UID_N/com.assistant.project.<service>
sleep 5
```

**NEVER restart `com.assistant.runner`, `com.assistant.bot`, or
`com.assistant.web`.** You are running inside the runner — restarting it
SIGTERMs your own session (exit 143). Only ever restart
`com.assistant.project.*` services.

### 5. Healthcheck gate — verify the new code actually serves

For each `kind: healthcheck` gate, hit its `path` and require its `expect`
status (default 200):

```bash
curl -so /dev/null -w '%{http_code}' --max-time 5 "http://localhost:<port>/<path>"
```

Read `<port>` from the manifest. A non-expected status → tail the service's err
log (`~/Library/Application Support/ai-server/volumes/logs/project.<slug>*.err.log`),
include the tail, and flag the deploy **DEGRADED**. Where practical, also probe
the actual change (curl the route you expect to have changed and grep the
response for the new behavior) — a green healthcheck with stale behavior is a
FAIL, not a pass.

Only when every gate ran green, the restarted services are RUNNING, and every
healthcheck met its `expect`, advance the deployed marker; a failed or
DEGRADED deploy leaves it untouched so the next run re-covers the range:

```bash
mkdir -p "$STATE_DIR"
git rev-parse HEAD > "$MARKER"
```

### 6. Summary (this becomes the job summary)

One paragraph: `RANGE_BASE→AFTER` deployed (note when the base came from the
marker — a prior run's undeployed work shipped now), each gate run + its
result, which services restarted, the healthcheck code, and whether the marker
advanced. If you stopped at a gate: exactly
what failed and where to look. Include the evidence commands + their output —
the acceptance evaluator re-checks claims.

## Quality gate (before you call it done)

- [ ] `--ff-only` pull; divergence reported, never forced
- [ ] Every declared gate run in order; a red test/build STOPPED the deploy
- [ ] Path-gated builds decided by the exact `when_paths` grep (outcome pasted)
- [ ] All ranges anchored on `RANGE_BASE` (deployed marker), never bare `BEFORE`;
      marker advanced only on a fully green deploy
- [ ] Only `com.assistant.project.*` services restarted (never runner/bot/web)
- [ ] Healthcheck code captured; DEGRADED flagged on any non-expected status
- [ ] No tracked-file writes/commits in the runtime clone
- [ ] Evidence (commands + output) in the summary

## Hard rules

- **Red gate → old code keeps running.** No exceptions, including "it's just a
  docs change" (docs ranges pass the gates anyway, so run them).
- **Never restart the runner/bot/web.** Only project services.
- **Never commit or edit tracked files in the runtime clone.** Code changes are
  born in the dev repo (dev-repo topology) or via `app-patch` (in-place) — never
  here. A runtime-born commit blocks all future deploys.
- **`--ff-only` always.** Divergence is a human decision, not something to force.

## Gotchas (living section — append when you learn something)

- **This is the generic engine; `atlas-redeploy` predates it.** Atlas has three
  services and a `web/`-gated Next.js build; until its manifest carries an
  explicit `delivery.deploy` block, keep using `atlas-redeploy`. New dev-repo
  projects should use this skill via their manifest contract.
- **A gate-failed deploy consumes the pull, not the marker** (atlas incident
  2026-08-17): the clone advances even on red gates, so ranges anchored on the
  current pull silently drop the failed run's paths. Anchor on the
  `deployed-sha-<slug>` marker; treat a no-op pull with a lagging marker as a
  real deploy.
- **Your cwd is the runtime clone** (the runner scopes deploy jobs there) — you
  do not need to `cd` into `projects/<slug>` yourself, but do confirm with
  `pwd` and `git remote -v`.
- **Logs live in the server log dir**, not the project:
  `~/Library/Application Support/ai-server/volumes/logs/project.<slug>*.err.log`.
- **Multi-service label format**: `com.assistant.project.<slug>-<service-name>`
  for sub-services (see the manifest `services` array); the primary service is
  `com.assistant.project.<slug>`.
