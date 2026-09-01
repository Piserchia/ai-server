# Charter — Atlas division

**Manager:** `atlas-manager`
**Charter (goal):** run the atlas product (private financials/trading dashboard +
agent platform) — its reports, scouting, briefs, portfolio interaction, and
deploys. Atlas is a product sub-org with its own dev-repo topology
(`~/Documents/repos/atlas`).

## Roster

| Agent | Role | Privilege | Purpose |
|---|---|---|---|
| `atlas-manager` | manager | read-only | Weekly atlas review: product/quality/ops gaps → proposals (Thu 06:00) |
| `atlas-report` | worker | content | Single expert report (stocks: three-lens pipeline) |
| `atlas-report-business` | worker | content | Business lens subagent of the atlas-report stock pipeline (dispatched via Task tool, not scheduled) |
| `atlas-report-technical` | worker | content | Technical lens subagent of the atlas-report stock pipeline (dispatched via Task tool, not scheduled) |
| `atlas-report-sweep` | worker | content | Weekly full report pass |
| `atlas-scout` | worker | content | Prediction-market / opportunity scan |
| `atlas-daily-brief` | worker | content | Daily portfolio brief |
| `atlas-portfolio` | worker | content | Portfolio interaction / Q&A |
| `atlas-k401-review` | worker | content | Weekly 401k review: per-holding fan-out + adversarial pass → k401_review report; recommendations only, no order path (Sat 13:00) |
| `atlas-k401-holding` | worker | content | Per-holding 401k analyst subagent (dispatched via Task tool, not scheduled) |
| `atlas-k401-adversary` | worker | content | Adversarial reviewer subagent of the 401k review (dispatched via Task tool, not scheduled) |
| `atlas-chat` | worker | content | Atlas conversational interface |
| `atlas-redeploy` | worker | prod-operator | Deploy atlas (bespoke pipeline; `project-redeploy` generalizes it) |
| `atlas-evaluate` | worker | content | Weekly loop governor: scorecard + data_gaps triage + build grading + built→live promotion + backlog re-route (Mon 11:00) |
| `atlas-build` | worker | guarded-writer | Twice-weekly loop builder: top eligible S/M item → workspace-isolated build → gates + code-review LGTM → push → deploy dispatch (Tue+Fri 10:00) |
| `atlas-gap-scout` | worker | content | Weekly top-gap free-source spec + live probe + builder-acceptance row (Wed 11:00) |
| `atlas-refresh-knowledge` | worker | content | Monthly knowledge curation + stale-claim re-verify (1st 11:30) |
| `atlas-momo-research` | worker | guarded-writer | Weekly Momentum-Lab research cycle: one governed hypothesis cycle in a workspace clone under momentum/evaluation/PROTOCOL.md; mechanics/IEX-observe until SIP approved (Thu 13:00) |
| `atlas-momo-drift` | worker | guarded-writer | Monthly Momentum-Lab retention-drift point (E-0028): anchored probe in a workspace clone, one dated JSON committed, data-only; monitoring not experiment (1st 13:30) |
| `atlas-swing-supervise` | worker | guarded-writer | Morning swing lifecycle run: executor --manage, verify resting exits/R12/R20/R21, report; sandbox-pinned until owner LADDER gate (~09:40 ET, dual DST rows) |
| `atlas-swing-trade` | worker | guarded-writer | Near-close swing decision run: bounded LLM selection over screener candidates, tighten-only, kernel places OTOCO; no-trade is success (~15:45 ET, dual DST rows) |
| `atlas-swing-research` | worker | guarded-writer | Weekly swing research cycle: one sealed card, backtest evidence, adversarial validation; additive-only write surface (Fri 13:00) |
| `atlas-swing-evaluate` | governor | guarded-writer | Weekly swing governor: DB-rows grade vs SPY/BIL, liveness sweep, deterministic demotions, ladder/shakedown memos (Sun 16:00) |
| `atlas-value-theses` | worker | guarded-writer | Weekly value-advisor deep run: fundamentals screen → gated thesis cards → shadow booking → owner DM; NO ORDER PATH (Mon 15:30 UTC, single row) |
| `atlas-value-monitor` | worker | guarded-writer | Daily open-thesis lifecycle sweep: invalidations/targets/21-DTE/expiry, shadow curve; alert on change only (weekdays 18:10) |
| `atlas-value-research` | worker | guarded-writer | Weekly advisor research cycle: one sealed card improving screen/thesis machinery; additive only (Tue 13:00) |
| `atlas-value-evaluate` | governor | guarded-writer | Weekly advisor governor: shadow-ledger grade vs SPY regime-annotated, process compliance dominates, STOP_READING authority (Sun 17:00) |
| `atlas-trader-paper` | worker | guarded-writer | Daily trader-vertical paper run: execute the deterministic executor in a workspace clone, verify + report; supervisor only, PAPER ONLY (weekdays 17:30) |
| `atlas-trader-research` | worker | guarded-writer | Weekly trader-vertical research cycle under trader/evaluation/PROTOCOL.md: card → backtest → adversarial validation → ledger + trial registry; additive strategy candidates only (Wed 13:00) |
| `atlas-trader-evaluate` | worker | guarded-writer | Weekly trader-vertical governor: grade the week vs SPY/BIL from DB evidence, lessons, gated stage flips (never toward live), liveness sweep (Sun 15:00) |
| `atlas-advisors-ingest` | worker | guarded-writer | Twice-weekly advisors ingest: RSS roster poll, yt-dlp transcripts, schema-validated claim extraction, dossier compaction; measurement-only, no order path (Mon+Thu 14:00) |
| `atlas-advisors-panel` | worker | guarded-writer | Weekly advisors panel: committed persona-mind emissions, deterministic book rebuild + SPY/BIL marks, digest w/ debate + liveness; measurement-only, graduation notes never wires (Sat 15:00) |
| `atlas-firm-rollup` | worker | guarded-writer | Daily firm-vertical deterministic run: firm.cli rollup+check+liveness in workspace clone, verify firm.* rows, breach-first risk-officer report; advisory only, writes only schema firm (weekdays 19:15) |
| `atlas-cio` | worker | guarded-writer | Weekly investment committee: firm spine + all governor grades → ONE attention-allocation memo (F-#### ledger entry + firm.decisions), owner DM digest; frozen evaluator, advisory ceiling per firm/FIRM_AUTHORITY.md (Mon 16:00) |

## Standards

- Single-writer: commits are born in the atlas dev repo (or the builder's
  per-job workspace clone, which pushes to the same GitHub master), deployed
  via `atlas-redeploy`; the runtime clone is pull-only (incident 2026-07-09).
- The closed improvement loop's binding contracts live in the atlas repo:
  `evaluation/LOOP.md` (state machine, single-writer-per-artifact, recovery
  matrix, human ceilings). Owner decision 2026-08-04: S/M builds + deploys
  are autonomous through the gated chain; `[system]`, paid sources,
  event-map pairs, auth/infra, destructive migrations, new deps stay human.
- **Open item (owner):** the atlas manifest lists `ANTHROPIC_API_KEY` in
  `env_required`; the server's rule is "never require an API key." Make atlas's
  key boundary explicit / remove the requirement (EVALUATION X2).
- `atlas-redeploy` should migrate onto the generic `project-redeploy` contract
  once atlas's manifest carries a `delivery` block.

## Cadence

Weekly (atlas review). Plus scheduled reports (daily brief 12:00, sweep Sun 18:00).

## Feedback / reports

Reads division-scoped job outcomes + `projects/atlas` docs; writes `REPORT.md`.
