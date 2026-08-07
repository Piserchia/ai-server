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

## Gap triage reference (2026-08-11)

- **platform calibration / options implied probs**: free via Kalshi/PM historical APIs + yfinance options → always triaged; only reject if the specific endpoint is confirmed 404 or paid-only.
- **resolution wording versioning**: always triaged — the text is already in the API response, it's a persistence gap.
- **GDX/GLD slope** and other ETF-based signals: always triaged — yfinance covers all ETF tickers free; no paid sources needed.
- **Futures-based gaps** (ZQ, term structure curves): check if yfinance has the ticker alive before triaging; ZQ 404'd in 2026 (rates_implied DEGRADED). Probe first.
