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
    local name="$1" cron="$2" kind="$3" desc="$4"
    local nxt next_sql
    nxt=$(next_slot "$cron")
    if [ -n "$nxt" ]; then next_sql="'$nxt'"; else next_sql="NOW()"; fi
    psql assistant -v ON_ERROR_STOP=1 <<SQL
INSERT INTO schedules (id, name, cron_expression, job_kind, job_description, paused, next_run_at, created_at)
VALUES (gen_random_uuid(), '$name', '$cron', '$kind', '$desc', false, $next_sql, NOW())
ON CONFLICT (name) DO UPDATE SET
    cron_expression = EXCLUDED.cron_expression,
    job_kind = EXCLUDED.job_kind,
    job_description = EXCLUDED.job_description;
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
# Weekly evaluate (Mon) triages the data_gaps ledger; gap-scout (Wed) specs the
# top triaged gap from a FREE source; refresh-knowledge (monthly) curates +
# re-verifies. 11:00-hour slots dodge the 12:00 daily-brief and Sunday sweeps.
upsert 'atlas-evaluate'          '0 11 * * 1'  'atlas-evaluate'          'atlas-evaluate: weekly project scorecard + data_gaps triage + backlog re-route (skills/atlas-evaluate)'
upsert 'atlas-gap-scout'         '0 11 * * 3'  'atlas-gap-scout'         'atlas-gap-scout: weekly top-gap free-source research + live probe + engineer-ready spec (skills/atlas-gap-scout)'
upsert 'atlas-refresh-knowledge' '30 11 1 * *' 'atlas-refresh-knowledge' 'atlas-refresh-knowledge: monthly knowledge curation + stale-claim reverification + gaps-sync (skills/atlas-refresh-knowledge)'

echo "Schedules seeded."
echo ""
echo "NOTE: review-and-improve runs via idle-queue trigger in events.py"
echo "      (up to once per day when no other jobs are queued), not via cron."
echo ""
psql assistant -c "SELECT name, cron_expression, paused FROM schedules ORDER BY name;"
