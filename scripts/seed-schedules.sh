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

echo "Schedules seeded."
echo ""
echo "NOTE: review-and-improve runs via idle-queue trigger in events.py"
echo "      (up to once per day when no other jobs are queued), not via cron."
echo ""
psql assistant -c "SELECT name, cron_expression, paused FROM schedules ORDER BY name;"
