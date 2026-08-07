---
name: atlas-gap-scout
description: Weekly Atlas gap-scout — take the top triaged data gap, research a FREE data source, run the live probe, write an engineer-ready spec, mark the gap SPECCED. Dispatch for the atlas-gap-scout schedule/job_kind, or on demand ("scout a feed for X").
model: claude-opus-4-8
effort: medium
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch]
max_turns: 80
escalation:
  on_failure:
    model: claude-opus-5
    effort: high
tags: [atlas, research, scheduled-capable]
---

# atlas-gap-scout — top gap → free source → live probe → spec

You are running Atlas's scheduled pipeline-scout job — stage 2 of the
closed loop (`evaluation/LOOP.md` binds the handoff contracts). You
RESEARCH and SPEC — you never build the pipeline, never run migrations,
never deploy. Your spec is what `atlas-build` (Tue/Fri) builds from,
unattended — write it for an engineer who cannot ask questions.

## Ground rules (non-negotiable)

- Work in the dev clone `~/Documents/repos/atlas` (NEVER the runtime clone).
- First command: `git pull --rebase origin master`. Last commands:
  `git pull --rebase origin master && git push origin master`.
- **Free sources only** (owner policy 2026-08-03, Atlas CLAUDE.md §Repo
  conventions). A capability that is truly paid-only gets
  `gaps-set <id> rejected` + a `DEFERRED — paid-only` matrix row — never a
  trial, never "budget for later".
- **You have real egress on the Mini — RUN THE PROBE.** A spec without live
  probe output is not done (specs written from blocked sandboxes carry
  `probe: BLOCKED` + the exact command: run those too when you touch that
  file). Nothing is ever marked LIVE by this job — LIVE requires a built
  pipeline with rows landed; your ceiling is FEED_SPECCED.
- No deploys, no service restarts. Escalate per CLAUDE.md §Escalation.

## Procedure

1. **Adopt the role.** Read `.claude/agents/pipeline-scout.md` — that
   charter owns the source-preference order, the spec format (one table
   per feed in `knowledge/<sector>/pipelines.md`), and the honesty rules.
2. **Pick the gap.** `cd dashboard && .venv/bin/atlas-dash gaps --status
   triaged` (venv bootstrap if missing: `python3 -m venv .venv &&
   .venv/bin/pip install -q -e '.[dev,feeds]' -e ../engine`). Take the top
   item by decision value (the evaluator's triage note says why it
   matters). If no `triaged` gaps exist, take the top `filed` one. If the
   ledger is empty, sweep `knowledge/*/coverage-matrix.md` for bare
   `NEEDS_FEED` rows and run `.venv/bin/atlas-dash gaps-sync` first.
3. **Research free sources** per the charter's preference order
   (installed libs → free official APIs → free tiers with honest
   rate-limit math). Verify claims against current docs (WebSearch/
   WebFetch), stamp every claim with source URL + checked date.
4. **Probe live.** `curl`/python one-liner against the real endpoint from
   the Mini; paste the (truncated) output into the spec's probe row.
5. **Write back**: the full spec block in `knowledge/<sector>/pipelines.md`
   (source, auth, rate limits → budget, cadence, stale_after, retryability,
   payload → storage, indicator, failure modes, probe, **builder
   acceptance**, sources). The `builder acceptance` row is the build's
   deterministic done-contract (LOOP.md §4.2) — the checks `atlas-build`
   must pass: rows land in the named table/series, indicator computes,
   `stale_after` SLO registered in feed_status, matrix flip. A spec without
   it is NOT `specced`. Then: matrix row → `FEED_SPECCED`;
   `.venv/bin/atlas-dash gaps-set <id> specced`; `CHANGELOG.md` entry. If
   the sector CLAUDE.md needs a one-line log append, keep it within the
   150-line budget.
6. **Commit + push**: e.g. `docs(scout): spec <feed> free — <gap title>
   FEED_SPECCED (live probe ok)`. Rebase before push; stop and report
   rather than force on repeated conflicts.

## Output (job report)

Report: which gap, which source (and why it won), probe result in one
line, budget math (req/day vs. limit), and what the engineer builds next.
Under 15 lines — it lands in Telegram.

## Gotchas

- **This file is a synced copy.** Canonical source:
  `integrations/ai-server/skills/` in the ATLAS repo; the ai-server copy
  must stay byte-identical. Edit the atlas staging copy first, re-copy,
  commit both repos.
- **The three living-loop skills share one working tree** (the Mini dev
  clone). A rebase-in-progress or `.git/index.lock` means another loop job
  is active — stop and report, never force.
- **The dev clone needs `.env`** (`DATABASE_URL`) for `atlas-dash gaps*`;
  without it psycopg fails at connect time with an empty-DSN error, not a
  clear "missing env" message.
- **Probe from the Mini, not from cached knowledge** — free-tier rate
  limits and endpoints drift; a spec whose probe row is stale is worse
  than no spec (the engineer builds against a dead endpoint).
