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
