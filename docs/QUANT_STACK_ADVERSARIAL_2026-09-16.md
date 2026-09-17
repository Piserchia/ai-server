# Quant stack — adversarial execution review (2026-09-16/17)

How the shipped quant validation-desk vertical matches (a) the source
blueprint (@x_insider4's "$200K quant stack" tweet + article) and (b) the
owner's original prompt. Method: five independent adversarial auditors
(blueprint coverage, from-scratch math recompute, prompt fidelity,
ceilings/process compliance, live-state probes), each instructed to REFUTE
every claim; findings below are what survived, plus the same-session
remediation each finding received. Full audit transcripts: workflow
`wf_db7ebe37-95c` (session artifacts).

## Verdict summary — the owner's prompt, clause by clause

| Clause | Verdict | Evidence |
|---|---|---|
| Take the tweet in steps / think it through | MET | Spec §1 decomposes 8 components + thesis (`docs/superpowers/specs/2026-09-16-quant-stack-design.md`) |
| Do research | MET | 7-agent research sweep; Bailey–López de Prado formulas verified against the primary PDFs; the 2014 paper's worked example ships as a golden test (DSR≈0.9004) |
| Document all portions of mimicking the setup | MET (money-logic PARTIAL, see F1) | Spec (approved-by-delegation), 12-task plan, quant/CLAUDE.md, quant/evaluation/PROTOCOL.md, registries, INDEX |
| Plan for the ai server | MET | `docs/superpowers/plans/2026-09-16-quant-stack-implementation.md`, committed + deployed |
| Turn-on switch | MET | Three layers, all proven live: fail-closed `enabled` flag (4 tests; only literal `true` arms), schedule rows pause/resume roundtrip exercised on the live DB, Rule-1 + grep tripwire wired into the deploy gate |
| Thorough tests on existing atlas Alpaca infra | MET | 73 tests; data via pre-existing `tradingcore.alpaca_data.DataClient`; the `@alpaca` smoke test is genuinely live (auditor forced it through a dead proxy → HttpError; real SPY bars in ~50ms otherwise) |
| Own-page decision ("up to you") | MET | Decision D4: `/quant` on atlas web (CF-Access private), 200 live with runs table, critic panel, health panel, memo |
| Implement thoroughly and correctly | MET (deviations honest, see F3–F7) | 8 blueprint components implemented with the blueprint's exact numbers (5+3 bps, DSR>0.95, 180/60, 1%/20%, 0.5×, 30-bar); DSR recomputed from scratch across all 8 reports — bit-exact; shift(1) structural and unbreakable by a peeking signal |
| Deploy | MET | server-deploy 72234f7d (gate 1418 green, schedules seeded) + atlas-redeploy d8ebab55 (12 commits, migration 0053, marker advanced) + remediation deploys; all verified via jobs table, audit logs, marker, live probes |
| Adversarial analysis + report | MET | This document + the five audit lenses; findings acted on same-session |

**End-to-end proof**: job `be356a36` ran the full scheduled shape (workspace
clone → env provisioning → ARMED preflight → sweep R-0005..R-0008 → health
pass → 1 commit pushed `7b9e3ef` → Telegram TL;DR) and the desk's first
live catch was its own: it filed **D-0001** (the lifetime-N ratchet, below)
as an owner DECISION-REQUEST instead of quietly patching thresholds.

## What the auditors tried to refute and could not

- DSR arithmetic: all 8 reports recomputed from their own stored inputs
  with independently written formulas — every diff 0.0 (<1e-6 bar); the
  raw-kurtosis convention (the classic bug) is correct; the paper's
  worked example reproduces 0.900397.
- The shift(1) law: a signal built with tomorrow's close earns nothing
  extra through the engine; hand-verified 3-bar arithmetic exact.
- Verdict law: every stored verdict re-derives from DSR/worst-fold/critic
  inputs; buy-and-hold SPY clears DSR (0.9876) and is still REJECTed on
  its −6.9% 2022 fold — the worst-fold gate has teeth.
- No order path: tripwire green + independent broader greps (order/buy/
  sell/submit/POST/tradier/executor/HTTP clients) — zero hits; only
  network path is the pinned `data.alpaca.markets` host.
- No protected path touched across all 17 quant commits (both repos).
- Append-only discipline: full `git log -p` over trials.jsonl + LEDGER.md
  — zero deleted lines ever; R-0001..4 untouched by the second sweep.
- Deploys real: jobs, audit JSONLs, deployed-sha marker, prod HEAD, and
  live page all cross-confirm; services hold live PIDs.

## Findings register

| # | Sev | Finding | Status |
|---|---|---|---|
| F1 | MED | **No revenue mechanism.** Nothing produces a dollar: reports aren't sold, a PASS promotes nothing (MISSION §M / INV-22 forbid an order path; atlas is CF-Access-private; no social publishing). The prompt's "making money through reports and automation" is fulfilled as automation + decision-support: the desk's money-logic is *not deploying noise* into the org's real-money-adjacent verticals and giving the owner deflated-truth memos (atlas mission priority 1). This was the spec's stated thesis (§2), not a silent shortfall. | ACCEPTED / disclosed — monetizing the reports beyond the owner's own use is an owner business decision outside the system's ceilings |
| F2 | MED | **/quant page went stale immediately**: the live sweep pushed R-0005..8 four minutes after the redeploy pinned the runtime clone, and nothing else pulls — the page would trail the desk by a week, every week. | FIXED — validate skill now dispatches a gated `atlas-redeploy` after each push (step 6, `needs-dispatch-mcp`); remediation redeploy surfaced R-0005..8 |
| F3 | MED | **Skill-copy drift within hours of birth**: the live run appended GOTCHAS (incl. the D-0001 ratchet warning) to the atlas staging copy; ai-server dev + prod copies lacked them. The two-repo byte-identity contract has no mechanical check — this will recur for every runtime learning. | FIXED for now (resynced byte-identical + deployed). Systemic gap remains: a `diff -qr` staging-vs-installed check in `lint_docs.py` would close it, but that file is a protected path — **owner decision** |
| F4 | MED→LOW | **Critic `fills` check was a hardcoded PASS** (spec promised an [l,h] containment assert). | FIXED — `data.bar_sanity()` audits every close/open against its bar's [low, high]; seeded-violation + clean-control tests added (73 tests) |
| F5 | LOW | **The DSR lifetime-N ratchet (D-0001)**: re-running an identical roster weekly appends 4 identical trials/run, so N ratchets and identical Sharpes deflate by calendar alone (sma_gate 0.9283→0.9157 in one day). Faithful to "count every trial", but "N trials" here isn't N independent tries — left alone the desk trends to all-REJECT regardless of merit. | OPEN — owner decision D-0001 (atlas `quant/evaluation/LEDGER.md`). Suggested resolution for the owner: count a `(family, params_hash)` pair once toward N (re-validation ≠ new search), a PROTOCOL §2 amendment |
| F6 | LOW | Dead sizing config; turnover/cost-drag computed but never surfaced; "folds positive" prose ambiguous; governor cadence 10:20 in two docs vs 12:20 shipped; Tradier-host tripwire blind spot; armed-at-birth vs "owner flips" tension. | ALL FIXED — sizing settings render in memos; turnover + cost drag in metrics.json + memo; "positive by return"; CLAUDE.md + spec amended (12:20, armed-at-birth delegation note); tripwire extended |
| F7 | INFO | `alignment` can't fail via the CLI path (inner-join by construction) and dropped-bar counts aren't reported; health machinery unexercised until a PASS exists (all 8 reports REJECT); `n_obs` off-by-one framing between memo header and critic evidence; zero schedule-fired runs yet (first: Sun 2026-09-20, Tue 2026-09-22); "gate 1418" rests on the deploy job's own summary; the plan doc retains the stale 10:20 cron (historical record, not amended). | DOCUMENTED — acceptable-by-construction or awaiting first scheduled fires; the schedule-adherence monitor + firm liveness rollup watch the `atlas-quant-*` rows automatically |

## Blueprint scorecard (tweet component → shipped)

1. Backtest engine — MET (pure-python instead of "vectorized/no loops": forced
   by the owner's stdlib ceiling, documented D2; every default number matches).
2. Metrics — MET (incl. underwater right-censoring the blueprint lacks).
3. Eight-way critic — MET; fills check now real (F4); alignment
   by-construction on the CLI path (F7).
4. Deflated Sharpe — MET, paper-verified, fail-closed on N≤0.
5. Walk-forward, worst-fold judgment — MET (+embargo, a superset).
6. Sizing + streak table — MET (−11.4%/−46.0% verbatim in every memo).
7. Production health check + pre-committed kills — MET in code and memos;
   "live" honestly redefined as fresh-data paper window (Rule 1); dormant
   until a PASS exists.
8. Five AI roles — PARTIAL by design (folded into worker+governor+roster,
   spec D7); the "state the economic MECHANISM" hypothesis discipline and
   the "Sharpe>2 = suspect" heuristic are not yet artifacts — candidates
   for a roster-card format if the owner wants them.

Core thesis shipped intact: **generation is free; validation is the job** —
and the desk proved it by rejecting all four of its own launch strategies.
