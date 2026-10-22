# Charter — MoneyMachine division

**Manager:** `mm-ceo`
**Charter (goal):** run the MoneyMachine Company — four domain buckets (etf,
longterm, shortterm, crypto) with one shared officer hierarchy (CEO, Research,
Bridging, Architect, Engineering, Execution) expressed as nine `mm-*` skills
parameterised by `bucket=`, researching, validating under the quant law and
shadow-running ways to make the owner money — reports only; INV-22: no order
path. Project repo `~/Documents/repos/moneymachine` (GitHub-canonical
`alfredbot-ai-butler/moneymachine`). Spec:
`docs/superpowers/specs/2026-10-21-moneymachine-company-design.md`; chartered
under the owner's 2026-10-21 delegation (spec §16 D0), not via the org CEO's
proposal lane.

## Roster

| Agent | Role | Privilege | Purpose |
|---|---|---|---|
| `mm-ceo` | manager | read-only | Company CEO: fetch origin, read every bucket's committed state, grades and ledgers plus liveness (psql SELECT over mm-* jobs, schedule_adherence.json) and spend; decide which buckets run this week and each governor's focus; dispatch at most max_governors_per_ceo_run mm-govern jobs; final text is the directive mm-report records. Read-only + dispatch, INV-20 hook-enforced (Sat 17:00 UTC) |
| `mm-govern` | governor | guarded-writer | Bucket CEO / frozen evaluator for ONE bucket: grades the last cycle from artifacts (independent DSR recompute), rewrites BACKLOG.md, opens the next cycle, dispatches exactly one stage within caps, files [system] items and DECISION-REQUESTs; mode=apply-system applies an owner-approved item to handbooks/BACKLOG only. Never researches or builds (dispatched by mm-ceo, not scheduled) |
| `mm-research` | worker | guarded-writer | Research EO: maintains knowledge/LIBRARY.md ("best way to make money in this domain") and writes one Research Brief RB-#### per cycle; arbitrage family first; prior-art across all atlas ledgers and all buckets; sourced, dated, graded claims (dispatch-driven, not scheduled) |
| `mm-bridge` | worker | guarded-writer | Bridging EO: turns a brief into ONE sealed Actionability Card AC-#### under company/PROTOCOL.md — deterministic rules, fenced live free-data probe, cost model, success/kill criteria with observables, placebo plan, trials registration; verdict ACTIONABLE / NOT-ACTIONABLE / BLOCKED-ON-DATA (dispatch-driven, not scheduled) |
| `mm-architect` | worker | guarded-writer | Architect EO: turns an ACTIONABLE card into an Architecture Plan AP-#### — module tree under buckets/<b>/projects/<name>/, interfaces, tests, acceptance rows including the validation-report row, reuse table (mmcore / adapters / quantlab), no new deps (dispatch-driven, not scheduled) |
| `mm-engineer` | worker | guarded-writer | Engineering EO: implements the plan — code + tests + quant-law validation report + acceptance evidence, ONE commit, in-session code-review LGTM, push; dispatches mm-execute only on a validation PASS; 2-attempt cap per cycle, blocker format (dispatch-driven, not scheduled) |
| `mm-execute` | worker | guarded-writer | Execution EO: runs the implementation's deterministic entrypoint, verifies outputs, marks the shadow book vs SPY/BIL with pessimistic fills, writes an Execution Report XR-####, routes issues to the governor; touches nothing else and dispatches nothing (dispatch-driven, not scheduled) |
| `mm-resume` | worker | read-only | Daily heartbeat: git show origin/main state for every bucket, finds stale (>6 h) or cap-stalled cycles and re-dispatches the exact stage within caps, double-dispatch guarded; writes nothing (daily 10:30 UTC) |
| `mm-report` | worker | guarded-writer | Reporting suite: records CEO decisions as C-#### company ledger entries, writes the weekly owner memo reports/weekly/<Saturday>.md (CEO FAILED is a headline, not a skip), monthly scoreboard from audit usage, answers the on-demand Telegram pull `latest`; never dispatches (Sat 19:30 UTC) |

## Standards

- **Rule 1 of the project `CLAUDE.md`** — no order path, no credentials, no
  paid data. Nothing in the repo or any `mm-*` skill places, modifies or
  cancels an order, holds or requests broker/exchange/API credentials, mounts
  a broker tool, or budgets for paid data; a validated strategy leaves the
  company only as a GRADUATION-OFFER ledger entry the owner carries through
  the target vertical's own front door (`company/MM_AUTHORITY.md`). Enforced
  by `shared/tests/test_no_order_path.py` at every preflight and gate
  (MISSION §M / INV-22).
- **Deterministic spine** — every number comes from committed code and
  `mmcore` (`PYTHONPATH=shared .venv/bin/python -m mmcore …`), never from
  in-session arithmetic; every CLI command prints a machine-readable verdict
  last; every handoff is a committed, pushed artifact with a parseable header.
- **One writer per artifact** (`company/LOOP.md` §2): each stage writes only
  its own artifact and ledger entry; nobody flips a stage they did not
  execute; stages close terminal outcomes; the governor grades every closed
  cycle and is the only mover graded -> closed (and the only writer of
  GRADE); ledger ids are strictly increasing and append-only (`mmcore ledger
  append` refuses edited history).
- **Caps are owner-owned** — `company/config/budget.yaml` (stage kinds only;
  governors, the resumer, the CEO and the reporter are never counted) is
  edited by the owner by hand; agents propose changes via a DECISION-REQUEST
  ledger entry. Dispatch only kinds matching `mm-*` with
  `payload.project_slug` = `moneymachine`; any other kind is a
  DECISION-REQUEST, never a dispatch (pinned by `tests/test_mm_skills.py`).
- **Front door = `company/LOOP.md` §7** (adopted from atlas
  `evaluation/LOOP.md` §7): `[system]` backlog item or DECISION-REQUEST →
  owner nod → applied by the owner's own reviewed commit or, for
  `company/officers/*`, `buckets/<b>/officers/*` and `BACKLOG.md` only, by
  `mm-govern mode=apply-system item=<n>` triggered from Telegram. SKILL.md
  files (beyond a Gotchas append), `LOOP.md`, `PROTOCOL.md`, `config/*.yaml`,
  tripwires, schedule rows, new buckets and family openings stay owner-only.
- **Three-layer switch** — `company/config/settings.yaml` `enabled:`
  (fail-closed in `mmcore.settings.is_enabled`, read at every preflight after
  sync), the schedule rows (`/schedule pause mm-ceo-weekly` and the other
  two; the seeder never un-pauses), and Rule 1 + the tripwire suite.

## Cadence

Weekly (company allocation + owner memo), daily (resumer heartbeat). All three
rows carry payload `{"project_slug":"moneymachine"}` and are seeded only by
`scripts/seed-schedules.sh`:

| Slot (UTC) | Schedule row | Kind | What |
|---|---|---|---|
| Sat 17:00 (`0 17 * * 6`) | `mm-ceo-weekly` | `mm-ceo` | Weekly allocation: read every bucket, dispatch at most 2 governors (free band 15:15–20:09 after `atlas-advisors-panel` 15:00) |
| Sat 19:30 (`30 19 * * 6`) | `mm-report-weekly` | `mm-report` | Owner memo 2.5 h after the CEO, written whether or not the CEO succeeded; monthly scoreboard on the first Saturday |
| daily 10:30 (`30 10 * * *`) | `mm-resume-daily` | `mm-resume` | Re-dispatch stale or cap-stalled stages within caps (clear of `alpha-governor` 09:30, `atlas-build` 10:00 Tue/Fri, the 11:00 loop block) |

Everything else (governors and the five stage kinds) runs by dispatch chain
within the caps in `company/config/budget.yaml` (phase 0: 4 stage jobs/day
company-wide, 2 per bucket per week, 1 active cycle per bucket, at most 2
governors per CEO run). Expected weekly load is about $25–45 list-equivalent
against a structural ceiling of 23 jobs (spec §12.1).

## Feedback / reports

- Every `mm-*` job's final text is a structured summary (spec §8.6: first line
  `<kind> <bucket|company> <cycle|week> <outcome>`, then at most 8 sentences,
  then `DECISION:` / `ASK-OWNER:` lines for the CEO) landing in
  `volumes/audit_log/<id>.summary.md`; `system-manager` reads the `mm-ceo`
  summaries in its monthly org review alongside the other division managers.
- `mm-report` turns the CEO's `DECISION:` lines into `company/LEDGER.md`
  C-#### entries and writes `reports/weekly/<Saturday>.md` (honest-expectation
  line, CEO status, per-bucket scoreboard, graduation offers, asks waiting on
  the owner, system improvements, spend vs ceiling) and
  `reports/monthly/<YYYY-MM>.md` in the project repo; the on-demand pull is
  `/task --project=moneymachine --kind=mm-report latest`.
- Per-bucket learning lives in-repo: `buckets/<b>/evaluation/LESSONS.md` (one
  line per terminal decision), `company/LESSONS.md` (cross-bucket), the
  governor's GRADE entry answering the three improvement questions (what went
  wrong, which contract line would have prevented it, the proposed fix) as
  numbered `[system]` items. `scripts/schedule-monitor.sh` DMs DARK/STUCK on
  the three rows with no change.
