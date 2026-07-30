#!/usr/bin/env bash
# scripts/seed-schedules.sh — insert canonical schedules. Safe to re-run (idempotent).
set -euo pipefail

upsert() {
    local name="$1" cron="$2" kind="$3" desc="$4"
    psql assistant -v ON_ERROR_STOP=1 <<SQL
INSERT INTO schedules (id, name, cron_expression, job_kind, job_description, paused, next_run_at, created_at)
VALUES (gen_random_uuid(), '$name', '$cron', '$kind', '$desc', false, NOW(), NOW())
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
upsert 'system-manager-monthly' '0 7 1 * *' 'system-manager' 'Monthly CEO org review vs MISSION'

echo "Schedules seeded."
echo ""
echo "NOTE: review-and-improve runs via idle-queue trigger in events.py"
echo "      (up to once per day when no other jobs are queued), not via cron."
echo ""
psql assistant -c "SELECT name, cron_expression, paused FROM schedules ORDER BY name;"
