#!/usr/bin/env bash
# scripts/seed-schedules.sh — insert canonical schedules. Safe to re-run (idempotent).
set -euo pipefail

# New rows first fire at their NEXT CRON SLOT, not immediately: seeding used
# NOW(), which made every newly introduced schedule due in the same 30s
# scheduler tick — a batch of new same-worktree schedules (atlas living
# loops, 2026-08-04) would run concurrently in one git clone. Existing rows
# are never touched (ON CONFLICT excludes next_run_at). Falls back to NOW()
# if croniter is unavailable so seeding can never hard-fail.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
next_slot() {
    (cd "$REPO_ROOT" && pipenv run python3 -c "
import sys
from datetime import datetime, timezone
from croniter import croniter
nxt = croniter(sys.argv[1], datetime.now(timezone.utc)).get_next(datetime)
print(nxt.replace(tzinfo=timezone.utc).isoformat())
" "$1" 2>/dev/null) || true
}

upsert() {
    # args: name cron kind desc [payload-json]
    # payload (optional, e.g. '{"project_slug":"atlas"}') is copied onto every
    # job the schedule enqueues — how a scheduled skill gets project scoping
    # (delivery-contract cwd + workspace isolation need job.payload.project_slug).
    # EVERY value reaches SQL as a psql bound variable (-v + :'x'), and the
    # heredoc delimiter is quoted so bash expands nothing — quotes/$() in any
    # arg can't break seeding or the shell (review 2026-08-05). Empty payload
    # → NULL via NULLIF; empty next-slot → NOW() via COALESCE. On conflict,
    # COALESCE keeps an existing payload when this script doesn't declare one
    # (out-of-band scoping survives re-seeds; declared payloads still win).
    local name="$1" cron="$2" kind="$3" desc="$4" payload="${5:-}"
    local nxt
    nxt=$(next_slot "$cron")
    psql assistant -v ON_ERROR_STOP=1 \
        -v n="$name" -v c="$cron" -v k="$kind" -v d="$desc" \
        -v p="$payload" -v nx="$nxt" <<'SQL'
INSERT INTO schedules (id, name, cron_expression, job_kind, job_description, job_payload, paused, next_run_at, created_at)
VALUES (gen_random_uuid(), :'n', :'c', :'k', :'d', NULLIF(:'p','')::jsonb, false, COALESCE(NULLIF(:'nx','')::timestamptz, NOW()), NOW())
ON CONFLICT (name) DO UPDATE SET
    cron_expression = EXCLUDED.cron_expression,
    job_kind = EXCLUDED.job_kind,
    job_description = EXCLUDED.job_description,
    job_payload = COALESCE(EXCLUDED.job_payload, schedules.job_payload);
SQL
}

upsert 'server-upkeep-daily' '0 3 * * *' 'server-upkeep' 'Daily server audit and upkeep'

# ── Management hierarchy (.context/org/) ───────────────────────────────────
# Department managers run weekly (read-only: evaluate their division → report
# with recommendations), staggered Mon-Thu so one review lands per morning.
# The connector reconciles the Delivery→Ops seam Friday. The CEO runs monthly
# (reconcile reports vs MISSION) — after a full week of division reports.
upsert 'ops-manager-weekly'       '0 6 * * 1' 'ops-manager'       'Weekly Platform Ops division review'
upsert 'delivery-manager-weekly'  '0 6 * * 2' 'delivery-manager'  'Weekly Delivery division review'
upsert 'knowledge-manager-weekly' '0 6 * * 3' 'knowledge-manager' 'Weekly Knowledge division review'
upsert 'atlas-manager-weekly'     '0 6 * * 4' 'atlas-manager'     'Weekly Atlas division review'
upsert 'delivery-ops-reconciler-weekly' '0 6 * * 5' 'delivery-ops-reconciler' 'Weekly Delivery->Ops seam reconciliation'
upsert 'insight-router-weekly'    '0 6 * * 6' 'insight-router'    'Weekly Knowledge/Atlas insight routing'
upsert 'system-manager-monthly' '0 7 1 * *' 'system-manager' 'Monthly CEO org review vs MISSION'

# ── Content cadence (Knowledge division) ────────────────────────────────────
# research-report was registered but never scheduled (T13 / registry remark;
# reconciler + knowledge-manager both flagged it). Weekly Monday 13:00 UTC.
upsert 'research-report-weekly' '0 13 * * 1' 'research-report' 'Weekly research report'

# ── Atlas report cadence (owner-visible daily/weekly reports) ───────────────
# These two rows predate this script's atlas section and lived ONLY in the DB
# (created out-of-band); a wipe+seed would have silently dropped the two most
# owner-visible atlas jobs (2026-08-31, EVALUATION_2026-08-30 F5.5). Crons
# match the live rows exactly.
upsert 'atlas-daily-brief'   '0 12 * * *' 'atlas-daily-brief'  'atlas-daily-brief: pre-open synthesis'
upsert 'atlas-weekly-reports' '0 18 * * 0' 'atlas-report-sweep' 'atlas-report-sweep: weekly full report pass'

# ── Atlas living loops (staged from atlas integrations/ai-server, 2026-08-03) ─
# The closed loop (atlas evaluation/LOOP.md, owner decision 2026-08-04):
# Mon evaluate (governor: triage, grade builds, built→live) → Tue build #1 →
# Wed gap-scout (spec) → Fri build #2 → Sun report sweep → Mon grades.
# 10:00/11:00 slots dodge the 06:00 managers, 12:00 daily-brief, Sunday sweeps.
# atlas-build carries job_payload.project_slug so the runner scopes it to the
# atlas dev repo (delivery contract) and gives it a per-job workspace clone
# (isolation: workspace) — the doc loops run unscoped in the shared dev clone.
upsert 'atlas-evaluate'          '0 11 * * 1'  'atlas-evaluate'          'atlas-evaluate: weekly project scorecard + data_gaps triage + build grading + built-to-live promotion + backlog re-route (skills/atlas-evaluate)'
upsert 'atlas-build'             '0 10 * * 2,5' 'atlas-build'            'atlas-build: twice-weekly top eligible backlog item -> isolated workspace build -> gates -> push -> gated deploy dispatch (skills/atlas-build)' '{"project_slug":"atlas"}'
upsert 'atlas-gap-scout'         '0 11 * * 3'  'atlas-gap-scout'         'atlas-gap-scout: weekly top-gap free-source research + live probe + engineer-ready spec with builder acceptance (skills/atlas-gap-scout)'
upsert 'atlas-refresh-knowledge' '30 11 1 * *' 'atlas-refresh-knowledge' 'atlas-refresh-knowledge: monthly knowledge curation + stale-claim reverification + gaps-sync (skills/atlas-refresh-knowledge)'
upsert 'atlas-momo-research'     '0 13 * * 4'  'atlas-momo-research'     'atlas-momo-research: weekly Momentum-Lab governed research cycle -> workspace clone, PROTOCOL.md binding, mechanics/IEX-observe until SIP approved (skills/atlas-momo-research)' '{"project_slug":"atlas","session_timeout_seconds":3600}'
upsert 'atlas-momo-drift'        '30 13 1 * *' 'atlas-momo-drift'        'atlas-momo-drift: monthly retention-drift point (atlas ledger E-0028) -> anchored probe via drift_probe.py in workspace clone, commit the ONE dated JSON, push; monitoring not experiment (skills/atlas-momo-drift)' '{"project_slug":"atlas"}'
# atlas-k401-review is a REPORT job against the runtime clone (atlas-report
# family): no project_slug payload, no workspace clone. Sat 13:00 is clear of
# every loop slot (Mon/Tue/Wed/Fri), Thu momo, Sun report sweep, 12:00 brief.
upsert 'atlas-k401-review'       '0 13 * * 6'  'atlas-k401-review'       'atlas-k401-review: weekly 401k holdings review -> per-holding analyst fan-out + adversarial pass -> k401_review report via atlas-dash save-report --k401; recommendations only (skills/atlas-k401-review)'
# ── Trader vertical (atlas trader/, 0042, 2026-08-26) ──────────────────────
# PAPER ONLY (atlas trader/CLAUDE.md rule 1). paper = daily executor
# supervision (workspace clone needs the project_slug payload — without it
# the runner clones the AI-SERVER repo); research = weekly governed cycle
# (workspace + 60-min budget); evaluate = weekly governor in the shared dev
# clone (no payload, atlas-evaluate posture). Slots: 17:30 weekdays is clear
# of every loop slot + 12:00 brief; Wed 13:00 clear (gap-scout is 11:00);
# Sun 15:00 is clear of the Sunday-evening report sweep (18:00, atlas-side)
# and lands before Mon 11:00 atlas-evaluate.
upsert 'atlas-trader-paper'      '30 17 * * 1-5' 'atlas-trader-paper'    'atlas-trader-paper: daily trader-vertical PAPER run -> deterministic executor in workspace clone, verify trader.runs row + reconciliation, report state/halts; supervisor only, never trades itself (skills/atlas-trader-paper)' '{"project_slug":"atlas"}'
upsert 'atlas-trader-research'   '0 13 * * 3'  'atlas-trader-research'   'atlas-trader-research: weekly governed trader research cycle -> pre-registered card, deterministic backtest evidence, adversarial validation, ledger + trial-registry close-out under trader/evaluation/PROTOCOL.md (skills/atlas-trader-research)' '{"project_slug":"atlas","session_timeout_seconds":3600}'
upsert 'atlas-trader-evaluate'   '0 15 * * 0'  'atlas-trader-evaluate'   'atlas-trader-evaluate: weekly trader governor -> grade the week vs SPY/BIL from DB evidence, lessons, gated stage flips (never live), schedule-liveness sweep (skills/atlas-trader-evaluate)'

# Advisors vertical (YouTuber persona shadow scoreboard, spec 2026-08-30):
# ingest Mon+Thu 14:00 UTC (clear of 11:00 loop slots, 12:00 brief, 13:00
# research slots); panel Sat 15:00 UTC (clear of k401 Sat 13:00 and
# trader-evaluate Sun 15:00). Measurement-only vertical — no order path.
upsert 'atlas-advisors-ingest'   '0 14 * * 1,4' 'atlas-advisors-ingest'  'atlas-advisors-ingest: twice-weekly advisors ingest -> RSS roster poll, yt-dlp transcripts, schema-validated claim extraction, dossier compaction, liveness row (skills/atlas-advisors-ingest)' '{"project_slug":"atlas","session_timeout_seconds":3600}'
upsert 'atlas-advisors-panel'    '0 15 * * 6'  'atlas-advisors-panel'    'atlas-advisors-panel: weekly advisors panel -> committed persona-mind emissions, deterministic book rebuild + SPY/BIL marks into advisors.*, weekly digest w/ debate + liveness (skills/atlas-advisors-panel)' '{"project_slug":"atlas","session_timeout_seconds":3600}'

# ── Swing + value verticals (atlas swing/ value/, 0044-0046, 2026-08-30) ───
# Spec v3: swing = auto-trader on Tradier (SANDBOX-PINNED until the owner
# LADDER.md funding gate); value = ADVISOR ONLY (no order path; shadow
# ledger). ET-anchored slots use DUAL MONTH-GATED rows (cron can't track
# DST): -edt covers Mar-Nov, -est covers Dec-Mar; the executor's off_window
# guard no-ops the off-season sibling, so exactly one effective run per day.
# Slots verified free: 13:40/14:40 + 19:45/20:45 weekdays, Fri 13:00,
# Sun 16:00/17:00, Mon 15:30, 18:10 weekdays. Supervise's window is
# narrowed to 09:35-10:25 ET so its overlap-month sibling (10:40 ET) falls
# off_window (code-review 2026-08-30) (map above; Mon 13:00 is
# research-report, 14:00 Mon/Thu advisors-ingest, Sun 15:00 trader governor).
upsert 'atlas-swing-supervise-edt' '40 13 * 3-11 1-5' 'atlas-swing-supervise' 'atlas-swing-supervise (EDT rows): morning lifecycle run ~09:40 ET -> executor --manage in workspace clone; verify resting exits/R12/R20/R21; report (skills/atlas-swing-supervise)' '{"project_slug":"atlas"}'
upsert 'atlas-swing-supervise-est' '40 14 * 1-3,11,12 1-5' 'atlas-swing-supervise' 'atlas-swing-supervise (EST rows): morning lifecycle run ~09:40 ET (skills/atlas-swing-supervise)' '{"project_slug":"atlas"}'
upsert 'atlas-swing-trade-edt' '45 19 * 3-11 1-5' 'atlas-swing-trade' 'atlas-swing-trade (EDT rows): near-close decision run ~15:45 ET -> screen, bounded LLM selection, kernel submit via executor (skills/atlas-swing-trade)' '{"project_slug":"atlas"}'
upsert 'atlas-swing-trade-est' '45 20 * 1-3,11,12 1-5' 'atlas-swing-trade' 'atlas-swing-trade (EST rows): near-close decision run ~15:45 ET (skills/atlas-swing-trade)' '{"project_slug":"atlas"}'
upsert 'atlas-swing-research' '0 13 * * 5' 'atlas-swing-research' 'atlas-swing-research: weekly governed research cycle under swing/evaluation/PROTOCOL.md -> one sealed card, backtest evidence, adversarial validation, ledger close-out (skills/atlas-swing-research)' '{"project_slug":"atlas","session_timeout_seconds":3600}'
upsert 'atlas-swing-evaluate' '0 16 * * 0' 'atlas-swing-evaluate' 'atlas-swing-evaluate: weekly swing governor -> DB-rows grade vs SPY/BIL, liveness sweep, deterministic demotions, ladder/shakedown memos (skills/atlas-swing-evaluate)'
# value-theses: ONE row (code-review 2026-08-30: value has no off_window
# guard, so dual rows would double-book in the March/November overlap; a
# weekly advisor doesn't need close-anchored precision — 15:30 UTC is 11:30
# EDT / 10:30 EST, always mid-morning RTH; weekly.emit is also idempotent
# per week as a second net).
upsert 'atlas-value-theses' '30 15 * * 1' 'atlas-value-theses' 'atlas-value-theses: weekly advisor deep run (Mon ~10:30-11:30 ET) -> screen, rule-bounded thesis cards, shadow booking, owner DM (skills/atlas-value-theses)' '{"project_slug":"atlas","session_timeout_seconds":3600}'
upsert 'atlas-value-monitor' '10 18 * * 1-5' 'atlas-value-monitor' 'atlas-value-monitor: daily open-thesis lifecycle sweep -> invalidations/targets/21-DTE/expiry, shadow curve; alert on change only (skills/atlas-value-monitor)' '{"project_slug":"atlas"}'
upsert 'atlas-value-research' '0 13 * * 2' 'atlas-value-research' 'atlas-value-research: weekly advisor research cycle under value/evaluation/PROTOCOL.md -> one sealed card, additive improvements (skills/atlas-value-research)' '{"project_slug":"atlas","session_timeout_seconds":3600}'
upsert 'atlas-value-evaluate' '0 17 * * 0' 'atlas-value-evaluate' 'atlas-value-evaluate: weekly advisor governor -> shadow-ledger grade vs SPY (regime-annotated), process compliance, STOP_READING verdict authority (skills/atlas-value-evaluate)'

echo "Schedules seeded."
echo ""
echo "NOTE: review-and-improve runs via idle-queue trigger in events.py"
echo "      (up to once per day when no other jobs are queued), not via cron."
echo ""
psql assistant -c "SELECT name, cron_expression, paused FROM schedules ORDER BY name;"
