# Firm WS2a — Risk-Book Spine Implementation Plan (atlas repo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `firm/` atlas vertical: migration `0049_firm.sql` (schema `firm`), deterministic nightly rollup of all five books into `firm.book_snapshots` + `firm.equity_rollup`, pure risk checks into `firm.checks`, adherence-JSON ingest into `firm.role_liveness`, the advisory ceiling (`CLAUDE.md` Rule 1 + guard test + `FIRM_AUTHORITY.md`), and the manifest deploy gate.

**Architecture:** `trader/` vertical template; `dashboard`-style psycopg3 for DB I/O (the ledgerlink psql-subprocess idiom doesn't fit multi-table reads); pure transforms in `rollup.py`/`risk.py`/`liveness.py` tested on dict fixtures; one CLI (`firm/firm/cli.py`) as the sole writer of the four deterministic tables. Repo: `~/Documents/repos/atlas` (dev clone; rebase before start AND before push).

**Tech Stack:** Python 3.12, psycopg3, pyyaml, dbmate migrations, pytest+ruff.

**Spec:** ai-server `docs/superpowers/specs/2026-09-01-atlas-firm-org-design.md` (§WS2a)

## Global Constraints

- `git pull --rebase origin master` before starting and before pushing; migration number claimed only on origin/master — re-check 0049 is still free at push time.
- Schema changes ONLY via dbmate in `db/migrations/`; every statement additive/idempotent (0042-0046 convention).
- Advisory ceiling: no order path, no writes outside schema `firm`, `firm/` dir; owner-owned `firm/config/limits.yaml` never edited by agents.
- Frozen benchmark pair: every `firm.equity_rollup` row carries `spy_close`/`bil_close` (nullable only where the source vertical lacks it — value has SPY only).
- Conventional commits; small diffs; verification skills before "done" (`verify-migration`, `verify-pipeline` analogues = the tests here).

---

### Task 1: Migration `0049_firm.sql` + glossary seeds

**Files:**
- Create: `db/migrations/0049_firm.sql`

**Interfaces:**
- Produces: schema `firm` with `book_snapshots(day, book, capital, symbol, qty, price, value, price_source, details, UNIQUE(day,book,symbol))`, `equity_rollup(day, book, equity, cash, spy_close, bil_close, PK(day,book))`, `checks(day, check_name, status ok|warn|breach, details, UNIQUE(day,check_name))`, `role_liveness(day, schedule_name, status, last_expected, observed_job_at, PK(day,schedule_name))`, `decisions(id, ts, week, kind memo|decision_request|graduation_note, title, body, refs)`.

- [ ] **Step 1:** `cd ~/Documents/repos/atlas && git pull --rebase origin master && ls db/migrations/ | tail -3` — confirm 0048 is still the head; if not, renumber to head+1 everywhere in this plan.
- [ ] **Step 2:** Read the glossary-seed insert style at the bottom of `db/migrations/0041_k401.sql` and copy it exactly for the new terms.
- [ ] **Step 3:** Write the migration:

```sql
-- migrate:up
-- 0049: firm vertical — consolidated risk book (spec: ai-server
-- docs/superpowers/specs/2026-09-01-atlas-firm-org-design.md §WS2a).
-- Convention per 0042/0043: own schema, every statement additive/idempotent.
create schema if not exists firm;

create table if not exists firm.book_snapshots (
  id uuid primary key default gen_random_uuid(),
  day date not null,
  book text not null,
  capital text not null check (capital in ('real','paper','shadow')),
  symbol text not null,
  qty numeric,
  price numeric,
  value numeric not null,
  price_source text not null,
  details jsonb not null default '{}'::jsonb,
  unique (day, book, symbol)
);
create index if not exists idx_firm_snapshots_day on firm.book_snapshots (day);

create table if not exists firm.equity_rollup (
  day date not null,
  book text not null,
  equity numeric not null,
  cash numeric,
  spy_close numeric,
  bil_close numeric,
  primary key (day, book)
);

create table if not exists firm.checks (
  id uuid primary key default gen_random_uuid(),
  day date not null,
  check_name text not null,
  status text not null check (status in ('ok','warn','breach')),
  details jsonb not null default '{}'::jsonb,
  unique (day, check_name)
);

create table if not exists firm.role_liveness (
  day date not null,
  schedule_name text not null,
  status text not null,
  last_expected timestamptz,
  observed_job_at timestamptz,
  primary key (day, schedule_name)
);

create table if not exists firm.decisions (
  id uuid primary key default gen_random_uuid(),
  ts timestamptz not null default now(),
  week text not null,
  kind text not null check (kind in ('memo','decision_request','graduation_note')),
  title text not null,
  body text not null,
  refs jsonb not null default '{}'::jsonb
);

-- Glossary (copy exact insert style from 0041): firm book, capital type,
-- cross-book concentration, role liveness, decision request, advisory ceiling.

-- migrate:down
drop table if exists firm.decisions;
drop table if exists firm.role_liveness;
drop table if exists firm.checks;
drop table if exists firm.equity_rollup;
drop table if exists firm.book_snapshots;
drop schema if exists firm;
-- (glossary deletes matching the up-seeds, 0041 style)
```

- [ ] **Step 4:** Apply + idempotency check: `dbmate up`, then re-run the up body via `psql atlas -f <(sed -n '/migrate:up/,/migrate:down/p' db/migrations/0049_firm.sql | grep -v 'migrate:')` — zero errors expected. Verify `psql atlas -c '\dt firm.*'` lists 5 tables.
- [ ] **Step 5:** Commit: `git add db/migrations/0049_firm.sql && git commit -m "feat(firm): migration 0049 — firm schema (book_snapshots, equity_rollup, checks, role_liveness, decisions) + glossary seeds"`

---

### Task 2: Vertical scaffold + advisory-ceiling guard test

**Files:**
- Create: `firm/pyproject.toml`, `firm/CLAUDE.md`, `firm/config/limits.yaml`, `firm/firm/__init__.py`, `firm/firm/db.py`, `firm/tests/conftest.py`, `firm/tests/test_advisory_only.py`, `firm/evaluation/LEDGER.md`
- Modify: `manifest.yml` (deploy gate)

**Interfaces:**
- Produces: `firm.db.connect()` → psycopg connection from `DATABASE_URL` in atlas `.env` (copy the exact env-loading idiom from `dashboard/atlas_dash`'s db module); `FIRM_TABLES = {"book_snapshots","equity_rollup","checks","role_liveness"}` writer allowlist.

- [ ] **Step 1:** `firm/pyproject.toml` — copy `trader/pyproject.toml`, set `name = "firm"`, `dependencies = ["pyyaml>=6.0", "psycopg[binary]>=3.1"]`, packages include `["firm*"]`.
- [ ] **Step 2:** `firm/CLAUDE.md` in the swing/value lean form:

```markdown
# Firm vertical — consolidated risk book (advisory only)

You are in the firm vertical: the cross-vertical layer that measures the
whole book. Spec: ai-server docs/superpowers/specs/2026-09-01-atlas-firm-org-design.md.

**Rule 1 — advisory ceiling.** This vertical NEVER places orders, never
touches broker/order APIs, and never writes outside schema `firm` and this
directory. Graduation to any authority is `FIRM_AUTHORITY.md`, owner-only.
Enforced by `tests/test_advisory_only.py`.

**Rule 2 — deterministic spine.** Numbers come from `firm/cli.py` runs
(committed code), never from an agent's in-session arithmetic. The CLI is
the ONLY writer of book_snapshots/equity_rollup/checks/role_liveness;
`atlas-cio` is the ONLY writer of firm.decisions + evaluation/LEDGER.md.

**Rule 3 — frozen benchmark pair.** Every equity_rollup row carries
spy_close/bil_close (value's shadow book is SPY-only; that gap is recorded,
not papered over).

Owner-owned files agents never edit: `config/limits.yaml`, `FIRM_AUTHORITY.md`.

Run tests: `cd firm && .venv/bin/pytest -q`
```

- [ ] **Step 3:** `firm/config/limits.yaml`:

```yaml
# OWNER-OWNED. Agents never edit (firm/CLAUDE.md). Thresholds for firm.checks.
concentration:
  max_symbol_pct_of_firm: 25      # warn above, breach above 35
  breach_symbol_pct_of_firm: 35
drawdown:
  warn_pct: 10                    # per-book max drawdown since inception
  breach_pct: 20
staleness:
  warn_days: 3                    # newest snapshot/curve age per book
  breach_days: 7
```

- [ ] **Step 4:** `firm/tests/test_advisory_only.py` — the mechanical ceiling:

```python
"""Rule 1 guard: the firm vertical is advisory-only, forever-until-owner-edit.

Greps the package (not tests) for order-path tokens and non-firm writes.
Run: cd firm && .venv/bin/pytest tests/test_advisory_only.py -q
"""
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "firm"
SRC = "\n".join(p.read_text() for p in PKG.rglob("*.py"))

FORBIDDEN = [
    r"/v2/orders", r"/v1/accounts/.*/orders", r"submit_order",
    r"alpaca\.markets/v2/orders", r"api\.tradier\.com/v1/accounts",
    r"OrderRequest", r"place_order",
]

WRITE_RE = re.compile(
    r"(?is)\b(insert\s+into|update|delete\s+from|truncate)\s+([a-z_\"\.]+)")
ALLOWED_WRITE_PREFIX = "firm."


def test_no_order_path_tokens():
    for pat in FORBIDDEN:
        assert not re.search(pat, SRC), f"order-path token {pat!r} in firm pkg"


def test_sql_writes_only_touch_firm_schema():
    for verb, target in WRITE_RE.findall(SRC):
        tgt = target.strip('"')
        assert tgt.startswith(ALLOWED_WRITE_PREFIX), (
            f"firm package writes to {tgt!r} via {verb!r} — Rule 1 allows "
            f"writes to firm.* only")
```

- [ ] **Step 5:** `firm/evaluation/LEDGER.md` seed header (append-only, F-#### entries, modeled on trader's), and `manifest.yml`: add a gate matching the existing entries' exact syntax (read one first), `when_paths: ["firm/"]`, running `cd firm && .venv/bin/pytest -q`.
- [ ] **Step 6:** Bootstrap venv + run: `cd firm && python3.12 -m venv .venv && .venv/bin/pip -q install -e '.[dev]' && .venv/bin/pytest -q` → advisory tests pass (package has only `__init__.py`/`db.py` so far). Remember the macOS hidden-.pth gotcha: if editable imports fail, apply the sitecustomize rescue documented in atlas.
- [ ] **Step 7:** Commit: `feat(firm): vertical scaffold — advisory ceiling (Rule 1 + guard test), limits.yaml, manifest gate`

---

### Task 3: Book readers (`books.py`)

**Files:**
- Create: `firm/firm/books.py`
- Test: `firm/tests/test_books.py` (pure normalizers only)

**Interfaces:**
- Produces: `read_all(conn, day) -> dict[str, Book]` where `Book = {"book": str, "capital": str, "positions": list[Position], "equity": float|None, "cash": float|None, "spy_close": float|None, "bil_close": float|None}` and `Position = {"symbol", "qty", "price", "value", "price_source", "details"}`.
- Pure normalizers (tested): `norm_trader(snapshot: dict) -> list[Position]`, `norm_swing(lots: list[dict]) -> list[Position]`, `norm_value(theses: list[dict]) -> list[Position]`, `norm_k401(rows: list[dict]) -> list[Position]`, `norm_owner(valued: list[dict]) -> list[Position]`.

- [ ] **Step 1:** Write failing tests for the normalizers with realistic fixture dicts:
  - trader: `details->'positions'` shape `{SYM: {qty, market_value, avg_entry_price}}` (executor.py:212) → Position with `price_source="broker"`, `value=market_value`.
  - swing: `positions_lots` open rows; stock structures (`occ_symbol` null) → `value=qty*entry_price`, `price_source="entry"`; option structures → `value=risk_usd`, `price_source="risk_proxy"`, details carries structure/setup.
  - value: open `theses` → `value=abs(params->>'notional')` if present else quote-based `params` fallback, `price_source="shadow"`, details carries kind/state (read one real row during implementation and pin the fixture to it).
  - k401: `k401_current` rows → value column as-is, `price_source="snapshot"`.
  - owner: `valued_holdings()` dicts (asset_id, quantity, market_value, last_price) → `price_source="candles"`; rows with `market_value None` (no price) are skipped and counted in the reader's `details`.
- [ ] **Step 2:** Run tests, see them fail; implement normalizers; tests pass.
- [ ] **Step 3:** Implement the I/O readers around them: SQL per vertical copied from the authoritative sources — `swing.positions_lots where state='open'`; `value.theses where state='open'`; `trader.runs` latest `details ? 'positions'` (ledgerlink.py:64 SQL); `select * from k401_current`; owner via `from atlas_dash.holdings import valued_holdings` (dashboard venv is separate — instead re-implement its two queries in SQL: `_aggregated_holdings` + candles lateral join, copying `web/lib/atlas/queries.ts` `VALUED_SQL`'s SQL, since firm cannot import atlas_dash across venvs). Equity/cash per book: latest `trader.equity_curve` / `swing.equity_curve` / `value.shadow_curve` rows; owner/k401 equity = Σ position values.
- [ ] **Step 4:** Commit: `feat(firm): book readers — five books normalized to the firm position shape`

---

### Task 4: Rollup + risk checks + liveness (pure cores, CLI)

**Files:**
- Create: `firm/firm/rollup.py`, `firm/firm/risk.py`, `firm/firm/liveness.py`, `firm/firm/cli.py`
- Test: `firm/tests/test_rollup.py`, `firm/tests/test_risk.py`, `firm/tests/test_liveness.py`

**Interfaces:**
- `rollup.snapshot_rows(books: dict[str, Book], day: date) -> list[dict]` — pure; one row per position, plus per-book equity rows `equity_rows(books, day)`.
- `risk.run_checks(snapshots: list[dict], curves_by_book: dict[str, list[dict]], limits: dict, today: date) -> list[dict]` — pure; check names `cross_book_concentration`, `book_drawdown:<book>`, `staleness:<book>`, `benchmark_pair:<book>`; each `{"day", "check_name", "status", "details"}`.
- `liveness.rows_from_artifact(artifact: dict, day: date, prefix: str = "atlas-") -> list[dict]`.
- CLI: `python -m firm.cli rollup|check|liveness` — upserts (`insert ... on conflict ... do update`) into the four tables; the ONLY writer.

- [ ] **Step 1:** TDD the pure cores. Required test cases: concentration ok/warn/breach across two books sharing a symbol (use limits fixture 25/35); drawdown from a curve with a 12% dip (warn) and 22% (breach) using the `book_stats` max-drawdown fold (import from `tradingcore.marks` — see Step 2); staleness with a 5-day-old book (warn); `benchmark_pair:value` warns (SPY-only by design, details say "known gap"); liveness maps artifact statuses through unchanged and filters non-`atlas-` schedules.
- [ ] **Step 2:** Graduate `book_stats` + `_bench_return` from `advisors/advisors/marks.py` into `tradingcore/tradingcore/marks.py` verbatim (second use → shared lib rule); add `-e ../tradingcore` to firm's install; do NOT touch advisors' copy (recorded as later cleanup in the ledger seed).
- [ ] **Step 3:** Implement `cli.py`: `rollup` = read_all → snapshot_rows + equity_rows → upsert; `check` = read today's snapshots + curves from `firm.equity_rollup` → run_checks → upsert; `liveness` = read artifact path from `FIRM_ADHERENCE_JSON` env, default `~/Library/Application Support/ai-server/volumes/telemetry/schedule_adherence.json` → upsert. Each subcommand prints one `FIRM <cmd> day=<d> rows=<n> breaches=<n>` line and exits non-zero only on execution error (a breach is a successful measurement).
- [ ] **Step 4:** Full vertical suite green: `cd firm && .venv/bin/pytest -q && .venv/bin/ruff check .`
- [ ] **Step 5:** Live smoke on the Mini: `.venv/bin/python -m firm.cli rollup && .venv/bin/python -m firm.cli check && .venv/bin/python -m firm.cli liveness`, then `psql atlas -c "select book, count(*), sum(value) from firm.book_snapshots group by 1"` — expect rows for the books that have data today (trader/swing/value certainly; owner/k401 if priced).
- [ ] **Step 6:** Commit: `feat(firm): deterministic spine — rollup, risk checks, liveness ingest, CLI single-writer`

---

### Task 5: `FIRM_AUTHORITY.md` + LOOP.md ceiling + push

**Files:**
- Create: `firm/FIRM_AUTHORITY.md`
- Modify: `evaluation/LOOP.md` (§6 What-stays-human: one additive line)

- [ ] **Step 1:** Write `FIRM_AUTHORITY.md` on the GO_LIVE.md skeleton with the spec's gates: §0 honest-decision preamble (advisory may be the permanent right answer); §1 evidence preconditions — ≥8 consecutive weekly CIO memos grounded in complete rollups (zero DARK weeks in `firm.role_liveness`), ≥2 owner-confirmed real breach findings, 4 consecutive weeks with zero false-breach pages; §2 ignition edits (owner-by-hand, one reviewed commit; scope strictly defensive: pause schedules / set halts; never initiate or increase exposure); §3 automatic demotion to advisory on any false page (code, not judgment); §4 standing controls that work with the server dead.
- [ ] **Step 2:** Add to `evaluation/LOOP.md` §6: `- Firm-layer authority: the firm vertical is advisory-only; any authority flip is FIRM_AUTHORITY.md, owner-by-hand (2026-09-01).`
- [ ] **Step 3:** `git pull --rebase origin master` (re-check 0049 unclaimed), full gates (`cd firm && .venv/bin/pytest -q`; `cd web && npm run typecheck` untouched-ok), push `origin master`.
- [ ] **Step 4:** Update atlas `CHANGELOG.md` + `.context/CONTEXT.md` (Architecture: add firm vertical) in the same push.

## Self-review notes

- Spec coverage: 5 tables ✓ (spec's `firm.checks.check` column renamed `check_name` — `check` is a reserved word), books table ✓ (advisors excluded ✓), benchmark doctrine ✓, tradingcore graduation ✓, single-writer ✓, ceiling + guard test ✓, FIRM_AUTHORITY ✓, LOOP.md ✓, manifest gate ✓. Dashboard + agents are WS4/WS2b plans.
- Owner-equity note: owner/k401 books have no historical curve backfill — `equity_rollup` for them starts accruing from first run; `book_drawdown` checks skip books with <5 rows (encode in risk.py: `if len(curve) < 5: skip`).
- Value positions carry no qty/price in some kinds (msp/exit) — normalizer must not crash on params without notional; fall back to `value=0` with `details.unpriced=true` and let staleness/coverage surface it rather than inventing numbers.
