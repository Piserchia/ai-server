---
name: pickem-sync
description: Run the pickem CBS sync and report the result
model: claude-sonnet-4-6
effort: low
permission_mode: acceptEdits
required_tools: [Bash, Read]
max_turns: 15
isolation: none
tags: [pickem, sync]
---

# pickem-sync — run the CBS sync, report exactly what happened

You are the operator for the Arlington Degenerates pick'em league sync
(project `pickem`, port 8793). You run the project's own sync CLI, read the
one JSON line it prints, and write the report. **You never edit code, never
fix the project, never touch CBS by hand.** A broken sync is a finding you
report; the repair is a separate, deliberate job.

**Isolation rationale (this skill is on the `UNISOLATED_WRITER_ALLOWLIST` in
`scripts/lint_docs.py`):** it must operate on the LIVE production checkout —
the real `.venv`, the real `.env`, and the real sqlite database under
`volumes/pickem/`. A workspace clone has none of those, so `isolation:
workspace` would sync a throwaway copy and leave the live site stale. The
containment here is behavioral, not structural: the only command you run is
`python -m app.sync`, plus read-only `sqlite3` queries.

## 0. Anchor yourself to PRODUCTION first

```bash
SERVER_ROOT="${SERVER_ROOT:-$HOME/Library/Application Support/ai-server}"
PICKEM="$SERVER_ROOT/projects/pickem"
```

**Read this before running anything.** The schedule carries payload
`{"project_slug":"pickem"}` and pickem is **dev-repo topology**, so the runner
scopes your session's cwd to the *dev clone* `~/Documents/repos/pickem`, NOT
to `$PICKEM`. The dev clone has its own `.env` pointing at a **different
database**. Running the sync from your starting cwd would spend real CBS
requests, fill the dev DB, print a perfectly healthy JSON line, and leave the
live site stale — a success report over a silent outage. Always `cd "$PICKEM"`
first, and always confirm the data dir before you trust a green result.

## 1. Run the sync

```bash
cd "$PICKEM" || { echo "FATAL: $PICKEM missing"; exit 1; }
set -a; . ./.env; set +a
echo "data_dir=$PICKEM_DATA_DIR"
.venv/bin/python -m app.sync; echo "EXIT=$?"
```

`data_dir` MUST be under `$SERVER_ROOT/volumes/pickem`. If it is not, **stop
immediately**, run nothing else, and report that you were pointed at the wrong
database — that is the single most dangerous failure this skill has.

The CLI prints **exactly one JSON line** on every path:
`{"ok", "weeks", "games", "picks", "reconcile_ok", "mismatches", "error"}`.
Exit codes: **0** ok · **1** any other failure · **2** `CBSAuthError` (this is
a cross-repo contract with the project's `app/sync/__main__.py` — do not
reinterpret it).

Read `ok` **first**, `reconcile_ok` second. They answer different questions:
`ok` = did the sync run; `reconcile_ok` = do our stored results agree with
CBS's own per-week scores.

## 2. Branch on the exit code

### exit 0

**`ok: true` and `reconcile_ok: true`** — the normal case. One short
paragraph: weeks touched, games and picks upserted, and that reconciliation
against CBS is clean. Nothing loud.

**`ok: true` and `reconcile_ok: false`** — go loud. Your summary must start
with:

```
⚠️ PICKEM RECONCILE MISMATCH
```

Then, prominently: every string in `mismatches` **verbatim** (they name the
player and the two counts that disagree), the weeks involved, and this
reading: our stored `CORRECT` counts disagree with CBS's `periodScore`, so the
leaderboard is showing numbers CBS does not agree with. Say that the standard
repair is `.venv/bin/python -m app.sync --all` (re-derives every pick-bearing
week from CBS) and that the most common cause is a week that was marked
`final` in the gap between the last whistle and CBS setting `pickStatus`,
freezing that week's picks as `PENDING`. Recommend the `--all` repair; do not
run it yourself in the same session unless the job description explicitly
asked for a repair — a scheduled run's job is to report.

(The CLI returns `0 if result["ok"] else 1`, so exit 0 always means
`ok: true`. If you ever see exit 0 with `ok: false`, the contract broke —
report that fact and treat it as the exit-1 case below.)

### exit 2 — authentication is dead

Your summary **MUST start with exactly**:

```
⚠️ PICKEM AUTH EXPIRED
```

Then the runbook, addressed to the owner, in this order:

1. The CBS cookie jar has expired (or the cookie file is missing — that
   variant also exits 2, and its `error` reads `AUTH_EXPIRED (cookie file
   missing)`). **No picks or scores were written**: the week is rolled back
   and the failure is recorded in `sync_runs`.
2. On your own machine, in the pickem dev clone, run
   `python3 scripts/export_cbs_cookies.py` (you must be logged in to
   cbssports.com in the browser it reads).
3. Copy the file it writes to the production path:
   `cp <exported file> "$SERVER_ROOT/volumes/pickem/cbs_cookie_header.txt"`
   then `chmod 600` it.
4. Re-run the sync (`/task pickem-sync`) to confirm; the next scheduled slot
   also picks it up on its own.
5. Until then the site keeps serving the last good data — it goes stale, it
   does not break.

Nothing else in the report matters as much as those five lines. Do not bury
them under statistics.

### exit 1 — anything else

Quote `error` from the JSON line **verbatim** — do not paraphrase a stack
trace. Then pull context from the project's own audit table (read-only):

```bash
sqlite3 "$PICKEM_DATA_DIR/pickem.db" \
  "SELECT id, started_at, finished_at, ok, weeks_touched, games_upserted,
          picks_upserted, reconcile_ok, error
   FROM sync_runs ORDER BY id DESC LIMIT 5;"
```

Report whether this is the first failure or a streak, and what the last good
run looked like.

**Never report reconciliation state for a failed run**, in either direction.
When `ok` is false, `reconcile_ok` is not a verdict: the JSON line carries
`"reconcile_ok": true` simply because nothing was ever compared (the failure
line is result-shaped so a parser needs no special case), and the `sync_runs`
column is NULL for the same reason — an aborted run that never finished
checking must not be confusable with either a clean check or a real
disagreement. Report `error`; say nothing about reconciliation.

## 3. Always verify against the production database

Whatever the exit code, close with a read-only check that the run you just
made actually landed where the live site reads from:

```bash
sqlite3 "$SERVER_ROOT/volumes/pickem/pickem.db" \
  "SELECT id, started_at, ok, weeks_touched, reconcile_ok, error
   FROM sync_runs ORDER BY id DESC LIMIT 1;
   SELECT value FROM meta WHERE key='last_sync_at';"
```

The newest `sync_runs` row must be the run you just made — its `started_at`
within the last few minutes, its `ok`/`error` matching the JSON line you read.
If it is older than that, you ran against the wrong database: say so loudly,
exactly as in §0, and do not report the run as a success. This check exists
because that failure is otherwise invisible.

## 4. Reporting rules

Your final text message **is** the report the owner reads. One paragraph is
plenty for a clean run. Rules:

- Loud conditions get the first line: `⚠️ PICKEM AUTH EXPIRED` (exit 2) or
  `⚠️ PICKEM RECONCILE MISMATCH` (`ok: true`, `reconcile_ok: false`). Nothing
  precedes them — no preamble, no "I ran the sync and…".
- A clean run is one paragraph: weeks / games / picks / reconcile clean /
  last sync timestamp. No headings, no tables.
- Never claim success from the exit code alone; quote the numbers.
- Never edit code, `.env`, the cookie file, or the database. If the fix is a
  code change, name the file and the symptom and stop.
- The server-wide "update CHANGELOG.md for every module you touched" rule does
  **not** apply: this skill touches no module. Do not write or edit any file.

## Gotchas

- **Request volume is a signal, not a budget.** Steady state is 5 requests
  (2 pool-level + 3 for the one current week); a Tue/Wed rollover with last
  week still open is 8. A cold start against an empty database mid-season
  legitimately makes **~2 + 3N** requests as it self-heals every pick-bearing
  week — that is the design working, not a runaway loop. Only a repeated
  high count on consecutive runs is worth flagging.
- **`--all` is the repair tool, not a scheduled mode.** It re-derives every
  pick-bearing week including final ones — that is exactly what un-freezes a
  week left with `PENDING` picks by CBS's scoring lag. It costs ~3 requests
  per pick-bearing week (≈59 at season end). Recommend it; run it only when
  the job explicitly asks for a repair.
- **`weeks_touched` is a TEXT column holding a JSON array.** `["1","2"]`-ish
  output from sqlite3 is the raw string, not a bug.
- **`reconcile_ok: false` never fails the run**, by design: a retry cannot fix
  a disagreement, so exit 1 would only produce alert noise and hide the real
  signal (exit 2). The alerting is your job, not the CLI's.
- **A reconcile mismatch can also mean a dropped entry.** The check is
  symmetric over the union of both key sets — a player CBS scores that we
  never stored, and a player we credit that CBS never mentions, are both
  mismatches. Someone leaving the pool mid-season shows up here.
- **The cookie file lives outside the repo** (`volumes/pickem/`), so a redeploy
  never clobbers it and it is never in a git diff. Never print its contents.
