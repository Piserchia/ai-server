# atlas-redeploy CHANGELOG

## 2026-08-28 — deploy 69be6b2..97bde6b

- Range: 5 commits — feat(trader): autonomous PAPER trading vertical (executor, risk, portfolio, signals, alpaca, ledgerlink, http); research T-0003 fixtures; test(dashboard) full-chain conftest hard-fail; docs/plans/knowledge (inert); trader test suite
- Migration 0042_trader.sql: applied (new trader tables)
- Gates: dashboard pytest 444 passed ✅ (env sourced with CREW_TEST_DATABASE_URL); pmedge pytest 67 passed ✅; trader pytest 76 passed + 5 skipped ✅ (first-time venv created); momentum gate SKIPPED (no momentum/ changes); web build SKIPPED (grep '^web/' → no matches)
- Services restarted: all three (atlas, atlas-dash-scheduler, atlas-pm-edge) → all RUNNING
- Healthcheck: / → 200 ✅
- Marker advanced to 97bde6b
- Note: trader vertical ships runtime code but has no launchd service — continuous paper trading is separate work

## 2026-08-24 — deploy ef6477d..69be6b2

- Range: 11 commits — retirement vertical (k401 schema migration 0041, /retirement page + upload API, Fidelity positions-CSV parser, k401 packet + k401_review report kind, scheduler drain hook, Nav link, knowledge base + policy + 3 charters, evaluation updates, CLI weekly-review support); plus hardening tip (skip negative-quantity rows)
- Migration 0041_k401: applied (additive — new tables + fund enum + glossary seeds)
- Gates: dashboard pytest 221 passed / 223 skipped ✅; pmedge pytest 45 passed ✅; momentum gate skipped (no momentum/ changes); npm run build ✅ (/retirement compiled)
- Services restarted: atlas (web) + atlas-dash-scheduler; pm-edge unchanged and RUNNING
- Healthchecks: / → 200, /retirement → 200 ✅
- Marker advanced to 69be6b2

## 2026-08-23 — deploy faae8a5..ef6477d

- Range: 1 commit (fix(stocks): canonical fiscal-period keys — EDGAR filed period-ends absorb yfinance calendar labels)
- Migrations: none (dbmate up — no-op)
- dashboard pytest: 215 passed, 193 skipped ✅ (new test_financials.py cases included)
- pmedge pytest: 45 passed, 22 skipped ✅
- momentum gate: skipped (no momentum/ changes)
- web build: skipped — grep '^web/' returned empty (no web/ changes in range)
- Restarted: atlas-dash-scheduler (dashboard/ changed); atlas + atlas-pm-edge already running
- Healthcheck: curl http://localhost:8791/ → 200 ✅
- Marker advanced: deployed-sha-atlas → ef6477dae7c666752bd049503c7a050bda4cd59b ✅

## 2026-08-22 — deploy cbec74e..075b63a

- Range: 3 commits (feat(market): intraday 15m candles; chore(skills): atlas-evaluate max_turns bump; docs(stocks): EDGAR UA gotcha)
- Migration 0040_intraday_candles.sql applied ✅ (CHECK now includes '15m')
- dashboard pytest: 212 passed, 190 skipped ✅ (new test_intraday.py included)
- pmedge pytest: 45 passed, 22 skipped ✅
- momentum gate: skipped (no momentum/ changes)
- web build: completed successfully ✅ (AssetChart 1D/5D/1Y switcher, candles API updates)
- Services restarted: atlas (pid 22021), atlas-dash-scheduler (pid 22023), atlas-pm-edge (pid 22026)
- Scheduler started with poll_minutes=15, 3 new jobs registered (poll-15m-stocks, poll-15m-crypto, prune-intraday)
- healthcheck: 200 ✅
- Marker advanced: 075b63a

## 2026-08-22 — deploy 122b4b2..cbec74e

- Range: 2 commits (feat(stocks): EDGAR earnings backfill + levels chart; chore(skills): momo-research updates)
- dashboard pytest: 210 passed, 188 skipped ✅
- pmedge pytest: 45 passed, 22 skipped ✅
- momentum gate: skipped (no momentum/ changes)
- web build: completed successfully ✅ (EarningsHistoryChart.tsx + portfolio assetId page)
- Services restarted: atlas (Next.js), atlas-dash-scheduler (new edgar-backfill weekly job)
- atlas-pm-edge: untouched, RUNNING ✅
- healthcheck: 200 ✅
- Marker advanced: cbec74e
