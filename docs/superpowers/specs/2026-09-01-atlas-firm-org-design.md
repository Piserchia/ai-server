# Atlas Firm — cross-vertical firm layer, oversight, role depth (design)

Status: **ACCEPTED** — owner approved Approach 1 ("firm vertical with a
deterministic spine") and the sequencing in the 2026-09-01 brainstorming
session. Authority decision: **advisory + graduation gates**.

## Purpose

Atlas already runs as a firm-shaped org on paper: 32 rostered agents, four
vertical governors, a builder loop, sector knowledge packs. What is missing is
the layer that makes it a *business* rather than five parallel desks:

1. **Firm layer** — nothing consolidates the books. There is no cross-vertical
   risk book, no unified P&L attribution, no role that sees "the whole firm"
   the way `experts_charters/portfolio_strategist.md` describes seeing the
   whole portfolio.
2. **Oversight that works** — the 08-20 audit class: a scheduled role can go
   dark silently. The 529-as-completed bug is fixed (session.py terminal-banner
   classifier, 08-21), but **nothing answers "did runs happen at all?"** —
   `schedule_rollup` only grades runs that exist.
3. **Role depth** — agents have SKILL.md prompts; the firm roles need real
   charters (mandate, method, deliverable contract, escalation).
4. **Visibility** — the firm must be manageable from the dashboard: books,
   risk checks, role liveness, decision log.

Design principle (owner-approved): **deterministic code measures, agents
judge.** Every number the dashboard shows comes from committed, reproducible
computation (the momentum-lab lesson); LLM roles read those numbers and write
memos, never the reverse.

## Decisions taken (owner-approved in brainstorming)

- Approach 1: firm layer is a new atlas vertical `firm/` with its own schema,
  package, tests, and deploy gate — same template as `trader/`.
- Authority: **advisory day 1**. The CIO produces memos and decision requests;
  it moves no capital and pauses nothing. `FIRM_AUTHORITY.md` documents the
  graduation gates under which it could later earn *defensive-only* authority
  (LADDER.md-style evidence bar). The ceiling is `firm/CLAUDE.md` Rule 1 plus
  a mechanical no-order-path/no-mutation test, per the value-vertical
  precedent, and is added to `evaluation/LOOP.md` §6 (additive — a new
  restraint, never a relaxation).
- Oversight monitor is **server-side, out-of-band, deterministic**: a
  `scripts/` + launchd timer watchdog, not a schedules-table row (the
  scheduler cannot watchdog itself — rationale already codified in
  `healthcheck-all.sh:140-145`).
- Sequencing: WS1 monitor → WS2a firm spine + WS4 minimal dashboard →
  WS2b CIO/risk agents → WS3 handbooks (progressive).

## WS1 — Schedule-adherence monitor (ai-server)

**Logic** — new pure module `src/runner/schedule_adherence.py`, mirroring the
`schedule_rollup` style (plain dicts in, rows out, injected `now`):

`adherence_report(schedules, jobs, now, window_days=14) -> list[Finding]`
with finding kinds:

- `DARK` — unpaused schedule whose latest expected cron slot (croniter,
  fixed 3h grace) has **no job row** joined by `schedule_id`. Covers scheduler-task death, phase-shift after outage
  (`next_run_at` rebases off `now`, silently collapsing missed slots), and
  hand-paused-then-forgotten rows.
- `NEVER_RAN` — expected ≥ 1 fire in window, zero job rows ever
  (the "scout never ran" class).
- `FAILURE_STREAK` — ≥ 3 consecutive terminal failures (rollup computes the
  streak; nothing alerts on it today).
- `STUCK` — non-terminal job older than 2× the schedule's session timeout
  (default 24h) — the stranded-`running`/`awaiting_user` class.

**Delivery** — `scripts/schedule-monitor.sh`: thin wrapper, `pipenv run
python -m src.runner.schedule_adherence` against the assistant DB, prints a
report, DMs the owner via the `healthcheck-all.sh` raw-curl Telegram pattern
(works with runner/bot dead), epoch-file rate-limited, `SILENT` when clean
except a Sunday always-report. Scheduled by launchd
`install_timer "schedule-monitor" ... StartCalendarInterval 07:15` local.
Also writes `volumes/telemetry/schedule_adherence.json` (latest findings +
per-schedule expected/observed) so other consumers (WS2a) can read it without
re-deriving cron math.

Docs: SYSTEM.md module graph, hosting CONTEXT.md, runner CONTEXT.md,
`lint_docs.py` compliance. Tests: `tests/test_schedule_adherence.py`, pure
fixtures, frozen NOW, incident-shaped cases (08-17 governor-dark, scout
never-ran, phase-shift after 3-day outage).

## WS2a — `firm/` vertical spine (atlas repo)

Template: `trader/` layout; leanest-CLAUDE.md form (`swing/`, `value/`).

```
firm/
├── CLAUDE.md            # Rule 1: advisory only — never places orders, never
│                        #   edits another vertical's files/config/schedules
├── FIRM_AUTHORITY.md    # graduation runbook (see Governance)
├── pyproject.toml       # name = "firm"; dev deps pytest+ruff; -e ../tradingcore
├── config/limits.yaml   # OWNER-OWNED firm limits (concentration %, staleness
│                        #   days, per-book drawdown alert thresholds)
├── firm/
│   ├── books.py         # per-book readers → normalized Position/Curve dicts
│   ├── rollup.py        # nightly: snapshots + equity rollup (writes firm.*)
│   ├── risk.py          # pure checks: (snapshots, curves, limits) → findings
│   ├── liveness.py      # ingest schedule_adherence.json (atlas-* rows)
│   │                    #   → firm.role_liveness; path from
│   │                    #   FIRM_ADHERENCE_JSON env, default the production
│   │                    #   checkout's volumes/telemetry/ path
│   └── cli.py           # `firm rollup` / `firm check` entrypoints
├── evaluation/LEDGER.md # append-only F-#### entries (CIO memos, decisions)
└── tests/
```

**Books (v1)** — each tagged with `capital`:

| book | capital | positions source | equity curve source |
|---|---|---|---|
| owner | real | `holdings`+`assets` (VALUED_SQL logic via `atlas_dash.holdings`) | computed at rollup (Σ value; candles `latest_close`) |
| k401 | real | `k401_current` view | computed at rollup |
| trader | paper | `trader.runs` latest `details->'positions'` | `trader.equity_curve` |
| swing | paper | `swing.positions_lots` open | `swing.equity_curve` |
| value | shadow | `value.theses` open | `value.shadow_curve` (SPY only — noted) |

Advisors stays out of the risk book (it is a measurement scoreboard of other
people's picks); the dashboard links to its existing page.

**Schema** — `db/migrations/0049_firm.sql`, schema `firm`, additive +
idempotent:

- `firm.book_snapshots(id, day, book, capital, symbol, qty, price, value,
  price_source, details jsonb)` — one row per position per book per day.
- `firm.equity_rollup(day, book, equity, cash, spy_close, bil_close,
  PK(day, book))` — the advisors composite-key curve shape; frozen benchmark
  pair mandatory (trader/CLAUDE.md #7 doctrine).
- `firm.checks(id, day, check, status ok|warn|breach, details jsonb)` —
  daily risk-check results: cross-book symbol concentration (extends the
  `trading_shared.book_symbols` idea across all five books), per-book
  drawdown vs limits.yaml, data staleness, benchmark-pair presence.
- `firm.role_liveness(day, schedule_name, expected, observed, status,
  PK(day, schedule_name))`.
- `firm.decisions(id, ts, week, kind memo|decision_request|graduation_note,
  title, body, refs jsonb)` — structured mirror of LEDGER.md entries
  (the `value.grades` both-git-and-DB pattern).

P&L attribution math: graduate `book_stats()` (pure, currently in
`advisors/advisors/marks.py`) into `tradingcore/tradingcore/marks.py` —
second use, per the "graduate on second use" rule; advisors' copy is left
untouched (refactor later, noted, not done now). Prices: `candles`
`latest_close` where an `assets` row exists, else `tradingcore.alpaca_data`
daily close; `price_source` records which.

**Writers (single-writer per artifact):** `firm` CLI (deterministic) is the
only writer of `book_snapshots`, `equity_rollup`, `checks`, `role_liveness`.
`atlas-cio` is the only writer of `firm.decisions` + `evaluation/LEDGER.md`.
`config/limits.yaml` is owner-owned; agents never edit it.

manifest.yml gains a `kind: test, when_paths: ["firm/"]` deploy gate.

## WS2b — firm agent roles (skills; byte-identical two-repo copies)

| skill | cadence | role |
|---|---|---|
| `atlas-firm-rollup` | daily, weekdays 19:15 UTC (after trader-paper 17:30 and value-monitor 18:10) | Supervisor pattern (like `atlas-trader-paper`): execute `firm rollup && firm check` in the dev clone, **verify DB rows exist**, DM only on `breach` findings or execution failure. |
| `atlas-cio` | weekly, Mon 16:00 UTC (after governors Sun and `atlas-evaluate` Mon 11:00) | Investment committee. Reads: `firm.*` tables, `value.grades`, the four `evaluation/LEDGER.md` grade entries, `evaluation/SCORECARD.md`, `firm.role_liveness`. Writes: one F-#### allocation memo (LEDGER.md + `firm.decisions`) + owner DM digest. **Frozen evaluator**: never edits kernels, limits, schedules, or its own skill; all change proposals are DECISION-REQUEST entries. Leads with a liveness sweep (governor-dark doctrine). |

Charters: `firm/charters/cio.md` and `firm/charters/risk_officer.md` in the
`experts_charters` format ("You are Atlas's X / ## Your lens"), loaded via
skill `context_files`. The risk-officer charter governs how breach commentary
is written; the checks themselves are code.

Registration: skills staged in atlas `integrations/ai-server/skills/` +
byte-identical ai-server `skills/` copies; cadence rows added to
`scripts/seed-schedules.sh` (sole writer); atlas division `CHARTER.md` roster
+ `SKILLS_REGISTRY.md` updated.

## WS3 — role handbooks (progressive)

- `firm/charters/{cio,risk_officer}.md` (above) ship with WS2b.
- `knowledge/roles/README.md` + three archetype handbooks —
  `governor.md`, `researcher.md`, `supervisor.md` — distilling the discipline
  the vertical PROTOCOLs already share (frozen-evaluator rules, evidence
  requirements, benchmark doctrine, liveness-sweep-first, escalation ladder),
  ≤150 lines each, source-and-date claims, curated by the existing
  `atlas-refresh-knowledge` monthly loop. Existing skills gain one
  `context_files` pointer to their archetype handbook as they are next
  touched — no big-bang rewrite.

## WS4 — dashboard Firm section (atlas web)

- Nav: `["/firm", "Firm"]` in `Nav.tsx`. Page `web/app/firm/page.tsx` (RSC,
  `force-dynamic`, per-panel `.catch()` empty-states), queries in
  `web/lib/atlas/firm-queries.ts` (`server-only`, schema header, decimal
  strings end-to-end). No API routes needed (read-only RSC).
- Panels, in order: **Books** (per-book equity, capital tag, excess vs
  SPY/BIL via the lateral-join pattern from `advisors-queries.ts`);
  **Risk checks** (latest `firm.checks`, breach-first);
  **Cross-book overlap** (symbols held in >1 book, combined value);
  **Role liveness** (latest `firm.role_liveness`, dark-first);
  **Decision log** (latest `firm.decisions` memos/requests).
- Design-system + glossary gates apply: new on-screen terms (`firm book`,
  `capital type`, `cross-book concentration`, `role liveness`,
  `decision request`, `advisory ceiling`) get glossary entries in the same
  migration; `verify-frontend` + `scan_terms.py` must pass.

## Governance & graduation

- **Ceiling (now):** `firm/CLAUDE.md` Rule 1 — advisory only; no order path;
  no writes outside the `firm` schema, `firm/` dir, and its LEDGER; enforced
  by `firm/tests/test_advisory_only.py` (greps package for order-path
  imports/HTTP order calls; asserts ledgerlink-style writers touch only
  `firm.*`). Added to `evaluation/LOOP.md` §6 What-stays-human (additive).
- **`FIRM_AUTHORITY.md` (graduation runbook,** GO_LIVE/LADDER skeleton**):**
  §0 decide honestly whether the firm layer should ever hold authority;
  §1 evidence preconditions — ≥8 consecutive weekly CIO memos each grounded
  in complete rollup data (zero DARK weeks), ≥2 breach findings that the
  owner confirms were real and actionable, zero false-breach pages for
  4 consecutive weeks; §2 ignition edits (owner-by-hand, one reviewed
  commit): scope is **defensive only** — pause a vertical's schedule rows /
  set its `halts` row on breach; never initiate or increase exposure;
  §3 automatic demotion back to advisory on any false page; §4 standing
  controls that work with the server dead.
- Server-side: no ORG.md/ROLE changes beyond the atlas division CHARTER
  roster additions; no protected paths touched anywhere in this program.

## Testing

- WS1: `tests/test_schedule_adherence.py` (pure, incident fixtures) + full
  `pipenv run pytest` + `lint_docs.py`; server merge needs code-review LGTM
  (INV-13).
- WS2a: `firm/tests/` — pure rollup/risk transforms on dict fixtures;
  `test_advisory_only.py`; migration idempotency (re-apply 0049); benchmark
  pair presence asserted in rollup output.
- WS4: `npm run typecheck` + `verify-frontend` + glossary scan.
- End-to-end acceptance: one manual `firm rollup && firm check` run on the
  Mini producing rows for all five books; `/firm` renders them; the CIO's
  first memo cites those rows; monitor's Sunday report lists all atlas
  schedules as observed.

## Cut from v1 (YAGNI)

- No capital-allocation optimizer, position sizing, or rebalancing math —
  the CIO writes prose memos over deterministic numbers.
- No defensive authority day 1 (documented gate only).
- No VaR/correlation engine — concentration, drawdown, staleness only.
- No advisors books in the risk book; no pmedge/momentum books (no equity
  curves to roll up).
- No refactor of advisors onto `tradingcore.marks` (noted for later).
- No new notification infrastructure — reuse the curl-DM pattern and
  existing owner-DM skill conventions.
- No `firm.exposures` table — exposures computed at read time from
  snapshots.
