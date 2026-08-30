# Atlas Advisors — YouTuber persona shadow scoreboard (design)

Date: 2026-08-30 · Status: APPROVED (owner, in-session) · Owner gate cleared:
shadow-only scope, yt-dlp dependency, dashboard page in scope.

## Purpose

Track a curated panel of finance YouTubers as measurable "persona agents":
extract their explicit trade calls from video transcripts, additionally
simulate a distilled persona-mind per channel, run every persona as a
virtual (never-executing) portfolio, and score all of them against the
frozen SPY/BIL benchmark pair. Output: a weekly scoreboard + debate digest,
and — after ≥12 weeks — admissible post-cutoff evidence that can graduate a
persona or the consensus book into the governed trader research loop.

**This vertical executes nothing, anywhere.** It has no broker order path,
no connection to `trader/executor.py`, and never will. Trader constitution
rules 2 and 9 (no LLM output in the order path; LLM-signal strategies only
admissible on post-cutoff paper evidence) are preserved by construction:
this system *produces* exactly that post-cutoff evidence, outside the
execution surface.

## Decisions taken (owner-approved in brainstorming)

1. **Role**: shadow scoreboard (virtual books only). Not a sandbox broker
   account, not a digest-only toy.
2. **Mind fidelity**: two tiers per persona. Tier 1 = grounded (explicit
   on-video calls only). Tier 2 = simulated persona-mind (LLM loaded with a
   distilled dossier emits a full model portfolio weekly).
3. **Roster**: owner-curated, starts at ~5 channels, `config/roster.yaml`
   is owner-owned. Ships with a placeholder roster; ingest no-ops until the
   owner fills it.
4. **Hive layer**: consensus book (cross-persona agreement, its own virtual
   book) + weekly debate digest surfacing disagreements.
5. **Mind storage**: Approach A — distilled markdown dossiers + append-only
   `claims.jsonl` per persona; raw transcripts archived for audit and a
   possible future RAG layer. No vector store in v1.
6. **New dependency**: `yt-dlp` for transcript/caption fetch (owner
   approved). Video discovery uses YouTube channel RSS (free, keyless).

## Placement

New Atlas sector `advisors/` (peer of `trader/`, `momentum/`, `pmedge/`):

```
advisors/
  CLAUDE.md                    # constitution
  pyproject.toml               # package: advisors; deps stdlib+pyyaml+yt-dlp
  config/roster.yaml           # owner-owned channel list
  config/book_rules.yaml       # versioned deterministic book mechanics
  personas/<slug>/
    PERSONA.md                 # distilled worldview (compacted, rewritten)
    beliefs.md                 # dated current theses
    claims.jsonl               # append-only extracted calls (canonical)
    transcripts/<video_id>.md  # raw transcript + metadata header
  advisors/                    # python package (see Components)
  tests/
```

## Components

- `advisors/ingest.py` — RSS poll per roster channel; new-video detection;
  transcript fetch via yt-dlp subprocess; writes `transcripts/<id>.md`.
  Pure discovery/fetch — no LLM.
- `advisors/extract_schema.py` — claim record schema + validator. A claim:
  `{video_id, published_at, ticker, direction(long|exit|short_noted),
  conviction(1-3), horizon_days|null, thesis, quote}`. Invalid extraction
  fails the job (never silently dropped). Short calls are recorded as
  `short_noted` but NOT booked in v1.
- `advisors/books.py` — deterministic book mechanics:
  - Every book starts at $100k virtual; idle cash accrues the BIL proxy.
  - Tier 1: a long claim opens a 10%-of-book slot at the first session
    OPEN strictly after `published_at`; exit claims close the slot;
    default horizon 90 days then auto-close. Conviction recorded, not
    sized on, in v1.
  - Tier 2: weekly full rebalance to persona-mind target weights at the
    first session OPEN strictly after the git commit timestamp of the
    emission (no-look-ahead by construction).
  - Consensus: tickers held by ≥2 Tier-2 books; weight ∝ summed persona
    weights, renormalized; residual cash.
- `advisors/marks.py` — daily equity backfill for all books from Alpaca
  free daily bars (reuses the raw-REST pattern; no vendor SDK). Marks are
  reconstructable — no daily worker required.
- `advisors/consensus.py` — the ≥2-overlap aggregation (pure function).
- `advisors/report.py` — weekly digest renderer: scoreboard (all 11 books
  vs SPY/BIL since inception + trailing 4w), notable new claims, top
  disagreement, liveness warnings.
- DB migration `0043_advisors.sql` — schema `advisors`: `books`,
  `positions` (entry/exit, source claim or emission ref), `equity_curve`
  (daily marks per book). Single writer: the panel worker.

Canonical-data split: files in git (minds, claims, transcripts, digests)
are evidence; Postgres holds the derived scoreboard only.

## Loop workers (ai-server schedules; skills byte-identical two-repo copies)

- `atlas-advisors-ingest` — Mon+Thu 14:00 UTC, opus-4-8. Poll RSS → fetch
  new transcripts → LLM extraction pass per transcript (append claims,
  update `beliefs.md`, compact `PERSONA.md`) → validate → commit+push.
- `atlas-advisors-panel` — Sat 15:00 UTC, opus-4-8 (clear of k401 Sat
  13:00 and trader-evaluate Sun 15:00). Steps: (1) each persona-mind emits
  Tier-2 target weights (JSON, committed before pricing); (2) deterministic
  book updates (Tier 1 from new claims, Tier 2 rebalance, consensus);
  (3) mark backfill; (4) digest written to `advisors/reports/`;
  (5) liveness check — ingest must have run within 8 days, staleness is
  flagged in the digest (2026-08-20 loops-audit lesson: no silent-dark
  workers).

## Dashboard

`/advisors` page in the Next.js app (`web/`): scoreboard table of the 11
books vs SPY/BIL, per-book equity sparkline from `advisors.equity_curve`,
link/inline render of the latest digest. Read-only over the `advisors`
schema, following the existing portfolio-page patterns.

## Governance & graduation

- The vertical is measurement-only, permanently. `test_no_execution.py`
  asserts the package never imports trader execution modules and contains
  no order-endpoint strings (mirror of `tests/test_paper_only.py`).
- Graduation: after ≥12 weeks of post-cutoff marks, a book beating SPY
  risk-adjusted may be filed as a candidate into the Wednesday trader
  research loop — normal `trials.jsonl` entry, normal PROTOCOL validation,
  governor decides. Graduation is a ledger recommendation, never a wire.
- `config/roster.yaml` and `config/book_rules.yaml` are owner-owned;
  agents propose changes via ledger entry + owner nod.

## Testing

Pure-Python pytest (no network, canned fixtures): claim schema validation
(bad extraction rejected), Tier-1 open/close/horizon mechanics,
no-look-ahead invariant (constructed violations must be rejected),
consensus math, mark backfill against canned bars, `test_no_execution.py`.
Run: `cd advisors && python -m pytest -q`.

## Cut from v1 (YAGNI)

Conviction-weighted sizing; booking short calls; RAG/vector store over
transcripts; agent-discovered roster expansion; per-claim options/futures;
any daily worker.
