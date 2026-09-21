# atlas-evaluate — GOTCHAS

> Provenance: born untracked in the production checkout during the first live
> evaluator runs (2026-08-03/04) and rescued into the dev repo 2026-08-07 —
> sync-learnings skips untracked files, so it never published. The
> "2026-08-11" datestamps below are the writing session's error (that date
> hadn't occurred); content kept verbatim.

## Scanner must run AFTER sector research passes, not before (2026-08-11)

The glossary scanner was run at the START of the WP-5 arc and reported GREEN. The arc
then added coverage matrices for commodities, market, and shared sectors — all with
indicator slugs that don't match existing DB glossary entries (parameter-qualified slugs
like `sma-20-sma-50-sma-200` vs generic DB slug `sma`; plus 10+ new terms with no DB
entry at all). The scanner was not re-run before the commit, so the SCORECARD incorrectly
records "scanner GREEN".

**Fix pattern for all future evaluations:** Run the glossary scanner as the LAST step
before writing the SCORECARD entry, not as an early input. If any research passes or
sector expert work is done in the same arc that adds or edits coverage matrices, re-run
the scanner after those matrices are finalized.

## atlas-dash venv needs reinstalling on the dev clone each session (2026-08-11)

The `dashboard/.venv` exists on the dev clone but the editable install may not work via
the `atlas-dash` shebang script if site-packages aren't recognized. Use the full python path:

```
/Users/alfredbot.ai.butler/Documents/repos/atlas/dashboard/.venv/bin/python3 -m atlas_dash.cli gaps --status filed
```

Instead of just `.venv/bin/atlas-dash gaps --status filed`. The module IS correctly
installed but the editable finder sometimes doesn't resolve via the wrapper script. Always
test with `python3 -m atlas_dash.cli` not the script wrapper.

## DATABASE_URL must be set explicitly for atlas-dash CLI (2026-08-11)

The CLI reads DATABASE_URL from environment, not from `.env`. Even though `.env` exists
in the atlas repo root, the CLI does not auto-load it. Pass it inline:

```
DATABASE_URL="postgres://localhost:5432/atlas?sslmode=disable" .venv/bin/python3 -m atlas_dash.cli gaps ...
```

## Paid-only rejections go in PROSE, never in a coverage-matrix table row (2026-08-24)

The skill tells you to record a paid-only rejection with a `DEFERRED — paid-only` note in
the owning sector's coverage matrix. If that sector has no existing row for the thing, the
tempting move is to add one. **Don't add a table row.** The glossary scanner slugifies the
first cell of every `|`-table row in every coverage matrix, so a new row *mints a glossary
slug* — and the evaluator is forbidden from writing migrations, so it cannot define it. This
run added two paid-only rows to `knowledge/stocks/coverage-matrix.md` and flipped the scanner
from PASS to `RESULT: FAIL — 2 undefined terms` (`options-flow-institutional-positioning`,
`smartphone-handset-regional-market-share`) in the same session that was scoring itself on the
scanner. It is the identical defect class that made the 2026-08-10 evaluator's two paid-only
crypto rows cost a builder slot (migration 0039).

**Fix pattern:**
- The thing already has a row → *edit that row's status/notes in place* (this is what the
  crypto `exchange flows` downgrade did — safe, no new slug).
- The thing has no row → append a `## DEFERRED — paid-only` **prose section** with bullets.
  The scanner only reads table first-cells, so bullets are invisible to it. Say plainly why
  no free source exists, and name the LIVE free substitute that partially covers it.
- Either way, re-run the scanner AFTER the matrix edits (see the first gotcha) and before
  writing the SCORECARD — otherwise you grade yourself against a stale result.

## Do not trust a green deploy-gate pytest line (2026-08-24)

`dashboard/tests/conftest.py`'s `pg` fixture calls `pytest.skip()` when neither
`CREW_TEST_DATABASE_URL` nor `DASH_TEST_DATABASE_URL` is set. The deploy environment sets
neither, so ~193 DB-backed tests silently vanish and the gate reports a cheerful
"215 passed, 193 skipped ✅" over a suite that is actually RED. The tell is the passed-count
swinging between CHANGELOG entries (394 in one, 215 in the next) with no test churn between
them. When grading Verification & tests, **run the suite yourself on the dev clone with
DATABASE_URL loaded** — never quote the gate's number.

## Gap triage reference (2026-08-11)

- **platform calibration / options implied probs**: free via Kalshi/PM historical APIs + yfinance options → always triaged; only reject if the specific endpoint is confirmed 404 or paid-only.
- **resolution wording versioning**: always triaged — the text is already in the API response, it's a persistence gap.
- **GDX/GLD slope** and other ETF-based signals: always triaged — yfinance covers all ETF tickers free; no paid sources needed.
- **Futures-based gaps** (ZQ, term structure curves): check if yfinance has the ticker alive before triaging; ZQ 404'd in 2026 (rates_implied DEGRADED). Probe first.

## Triaging a several-hundred-gap sweep (2026-08-24)

The expert-report sweep filed **494** gaps in one 14-day window (188 the window before); the
count is growing and hand-moving each one is not viable inside the turn budget. What worked:

1. Dump `id8|source|title` to a temp file, then classify with an **ordered regex ruleset**
   into ~24 clusters. Order matters: put real-plumbing-defect rules first and the broad
   `not-disclosed` catch-all last, or the catch-all eats genuine work items.
2. Pick **one representative per cluster** to `triaged` and reject the siblings as duplicates
   with the representative's id **named in the reason string**. A cluster of 50 filings is
   one work item, not 50 — the ledger is a work queue, not a tally, and 494 open rows makes
   the next run's triage impossible.
3. Apply one row at a time via `atlas_dash.gaps.set_status`. It deliberately refuses bulk or
   ambiguous idents (an empty ident once matched and moved every open gap).
4. **`set_status` needs the pool initialised first** or every call fails with "db pool not
   initialized" — and it fails 494 times before you notice:
   ```python
   from atlas_dash import db as _db
   _db.init_pool(os.environ['DATABASE_URL'])
   from atlas_dash.gaps import set_status
   ```
5. Dry-run the plan and assert the transition count equals the row count and that the ids are
   unique, before passing `--apply`.
6. Add a fallback branch for "cluster whose representative I just triaged" — its siblings need a
   `duplicate of <rep>` reason, and without the branch the dry-run asserts `unrouted` and you lose
   a turn re-deriving why. Assert `not unrouted` explicitly; a silent unrouted row would otherwise
   be applied with a nonsense reason string.

## A job row with `status=completed` can be a total failure (2026-08-31)

atlas-build job `fad40175` ran **1.4 seconds**, consumed **0 tokens**, stored the summary
`"Not logged in · Please run /login"` — and resolved as `status=completed`. Because it is not a
failure row, no failure trigger fired, no escalation was sent, and self-diagnose never ran. The
loop silently lost a week of build capacity and the only reason it was ever visible is that this
run happened to read durations and token counts.

**When grading builds, never filter on `status`.** Read the shape of the row:

```sql
SELECT id, status, review_outcome,
       EXTRACT(epoch FROM (finished_at - started_at)) AS secs,
       total_tokens, result->>'summary'
FROM jobs WHERE resolved_skill='atlas-build' AND created_at > now()-interval '8 days';
```

A build session under ~60s or with 0 tokens did not build anything, whatever the status column
says. Treat it as a missed slot and file the `[ops]` item.

## `feed_status.last_success` only advances on ALL-symbol success (2026-08-31)

`ccxt:kraken` read STALE for 8 days with `error_count` 1,399 — which looks like a dead feed and was
written up as one last run ("CBETH has no market price"). It was not dead: `last_rows` was 80 and
12 of 13 symbols were polling fine. One failing symbol pins the whole source's `last_success`, so
the staleness signal is source-wide while the defect is symbol-wide.

**Read `last_rows` and `detail` before calling a source dead.** A source that is STALE but still
returning rows is a partial-failure bug (and the correct backlog item is two-part: fix the symbol
*and* make partial success advance `last_success`), not an outage.

## Commit BEFORE the closing rebase, not after (2026-08-31)

The skill says the last commands are `git pull --rebase origin master && git push origin master`.
Taken literally that fails: `error: cannot pull with rebase: You have unstaged changes`. Order is
stage → commit → `pull --rebase` → push. (The opening `git pull --rebase` at the top of the run is
on a clean tree and is fine.)

## Check deploy state by probing routes, not just comparing hashes (2026-08-31)

The existing gotcha says to compare the runtime clone's HEAD against `origin/master`. Do that, but
also probe the web surface on the port from `projects/_ports.yml` (atlas = **8791**, not 3001) and
check the live schema. This run found the combination that a hash diff alone understates: live
schema at migration 0046 while live *code* is three commits behind, i.e. schema leading code with
new schedules about to fire against it. `/portfolio` 200 + `/trading` 404 is the evidence line that
makes "pushed but undeployed" undeniable in a report.

## Shell cwd resets between Bash calls — source `.env` by ABSOLUTE path (2026-09-07)

`cd ~/Documents/repos/atlas && ... ; . .env` fails with `(eval):.:1: no such file or directory:
.env` because the working directory does not persist across tool calls the way you expect. The
failure is **silent in the thing that matters**: with no `DATABASE_URL`, the glossary scanner falls
back to a file-based `defined` set and reported **19 false undefined terms** this run before the
mistake was caught.

Always: `set -a; . "$HOME/Documents/repos/atlas/.env"; set +a` (absolute path), and chain with `&&`
inside one invocation. Sanity-check the scanner's own header line — it prints
`defined terms: N (source: db)`. If it does not say `source: db`, the result is garbage.

## `DASH_TEST_DATABASE_URL=$DATABASE_URL` is not how you run the suite (2026-09-07)

Pointing the test env var at the live DB yields `224 passed, 224 errors` with `RuntimeError: ref...`.
That is **conftest's live-DB guard working correctly** — `_ensure_test_db()` refuses any database
whose name does not end in `_test`. Do not "fix" it and do not report it as a red suite.

`unset DASH_TEST_DATABASE_URL CREW_TEST_DATABASE_URL` and let `resolve_test_db_url()` auto-derive
the sibling `<db>_test` from `DATABASE_URL`. Correct invocation this run: `1 failed, 447 passed`.

## Count coverage-matrix rows with a parser, never a grep (2026-09-07)

Published per-sector denominators had been wrong for at least one run: a naive `grep -c LIVE` counts
`DEFERRED — paid-only` **prose bullets**, section headers and note text as table rows, which is why
08-31 reported crypto 12/21 and stocks 26/32 against true values of 8/16 and 25/28.

Split each line on `|`, take the *status* cell, and match it exactly-equal-to or prefixed-by a status
token. Cross-check with a second stricter parser and hand-verify one sector before publishing. If the
numbers move a lot versus last run, suspect your predecessor's arithmetic before suspecting the repo.

## A gap at `specced` is not necessarily scout-approved (2026-09-07)

The builder trusts `specced` as "researched, probed, ready". But `atlas-refresh-knowledge`'s
matrix-sync can **insert gaps directly at `specced`**, skipping `filed`/`triaged` entirely — the
09-01 run created five that way, one of which (`16785548`, crypto exchange flows) resurrected an
owner-settled paid-only rejection whose matrix row has read `DEFERRED` since 08-24.

When sweeping `specced`, check provenance: a spec block must exist in the sector's `pipelines.md`.
No spec block = it is not really specced, and if the matrix row says `DEFERRED` you are looking at a
policy inversion, not a work item. Route it as a `[pipeline]` fix, not as buildable work.

## Ordered triage rulesets need specific-before-generic — and a per-cluster count check (2026-09-07)

In the 127-gap sweep, `3ab53b90` ("Insider activity not piped — ... would sharpen the OBV
distribution read") was captured by the `obv-subtrend` rule because a gap's *title* often mentions
the indicator it would improve, not the data it needs. Rules must be ordered by specificity of the
**subject**, not by how the text reads: `insider` above `obv-subtrend`, etc.

Never ship on `assert not unrouted` alone — that only proves everything matched *something*. Print
the per-cluster counts in the dry run and eyeball them; a cluster that swelled unexpectedly is a
mis-route. Leave an inline comment on any rule whose position is load-bearing, or the next run will
"tidy" it back.

## Grade the CONTENTS of a pending deploy range, not its size (2026-09-07)

Runtime `ce82c14` vs `origin/master` `6a3425d` looked alarming — 38 files, 65,666 insertions — and
last run's headline finding was exactly this shape. But `git diff --stat` on the range showed it was
**entirely research artifacts**: twelve multi-MB CSVs and dossier prose, no `src/` change and no
migration. That is deploy *lag*, which costs nothing, not deploy *drift*, which is a finding.

Read the range before scoring it. The line that separates the two is: does it contain a migration or
app code? If not, say so explicitly in the scorecard so the next run does not re-raise it.

## The `assistant` schema in this file's example SQL is wrong — check `\d` first (2026-09-14)

Three column names used by the procedure's own example queries do not exist:

- `jobs.finished_at` → the column is **`completed_at`**
- `schedules.cron` → the column is **`cron_expression`**
- `feed_status.status` → there is **no** status column. Derive freshness:
  `CASE WHEN last_success IS NULL THEN 'NEVER'
        WHEN now()-last_success > stale_after THEN 'STALE' ELSE 'FRESH' END`

And in the `atlas` DB the domain tables are **plural**: `assets`, `holdings` (not `asset`/`holding`).
Open with `psql assistant -c '\d jobs'` / `\dt public.*` rather than trusting a remembered column
name; each wrong guess costs a round trip and the psycopg error names the column, not the fix.

## macOS has no `shuf` and no `timeout` (2026-09-14)

Both appear in habit-formed one-liners and both fail with `command not found` on the Mini. Sample a
file with `awk 'NR%36==1'` instead of `shuf -n`; for pytest just run it without a timeout wrapper
(the suite is ~45s). `gtimeout` exists only if coreutils is installed — do not assume it.

## A `completed` job can leave its whole output uncommitted in the shared tree (2026-09-14)

The 09-13 `atlas-value-evaluate` job wrote a complete G-0004 grade into `value/evaluation/LEDGER.md`
and exited `completed` without committing. This run met it as
`error: cannot pull with rebase: You have unstaged changes` on the opening command.

Do **not** stash or discard. Check for a live sibling first (`.git/index.lock`, rebase-in-progress,
and the owning job's status in `jobs`) — if a job is still running, stop and report per the
shared-working-tree rule. If the owner has finished, the content is orphaned work: commit it
**verbatim** under its own message attributing the originating job, then proceed with your pull. It
is also a `[ops]`-class finding for the scorecard, not just a chore.

## Closing order is stage → commit → pull --rebase → push (2026-09-14)

The SKILL text reads `git pull --rebase origin master && git push origin master` as the last
commands. Taken literally that fails on your own dirty tree — you have just written the scorecard,
the backlog, the matrices and the CHANGELOG. Commit first, then rebase, then push.

## Coverage-matrix status parsing: `LIVE-with-signal` is the trap (2026-09-21)

Counting LIVE rows per sector looks like a one-line grep and is not. Three stocks rows and four
crypto rows read **`LIVE-with-signal`**, and a strict `cell == "LIVE"` test drops them silently —
this run's first parser reported crypto 5/13 and stocks 22/26 against the previous run's 8/16 and
25/28. Nothing errors; you just publish a fabricated regression.

Three rules for the parser, all learned the hard way here:

1. Match on a **word boundary**, not a prefix: `re.match(rf"^{tok}\b", up) or up.startswith(tok+"-")`.
   A bare `up.startswith(tok)` is worse than useless — my *cross-check* script used it and
   confidently reported zero unmatched rows while three rows were being dropped.
2. Order the token list so **`LIVE` is LAST**. `PIPELINE_BUILT`, `FEED_SPECCED`, `DEFERRED` and
   `DEGRADED` must all get first refusal, otherwise a status containing the substring wins early.
3. Make the parser print an **UNMATCHED list that must be empty**, and skip the header row
   explicitly (`cells[0].lower() == "indicator"`). A count with no unmatched-row assertion is an
   unverified count.

Then reconcile against the previous scorecard entry before writing. A sector count that moves by
more than the promotions you personally made this run is a parser bug until proven otherwise.

## Rank the backlog for the builder's selection rule, not for your own sense of priority (2026-09-21)

`atlas-build` takes the **topmost builder-eligible item** and a window has ~2 slots. An item parked
at slot 4 with a green probe and a READY spec is not "queued" — it is **unreachable**, and it will
stay unreachable forever while you keep writing "carried, still unpicked" in the scorecard.

Commodities proved this over **seven consecutive windows**: EIA petroleum and CFTC COT sat at slots
4–5 the whole time, and five separate scorecards blamed throughput. Throughput was never the cause;
the ordering was, and the ordering is the evaluator's own lever. If you have written "still unpicked"
about the same item twice, stop diagnosing the builder and **move it to slot 1**.
