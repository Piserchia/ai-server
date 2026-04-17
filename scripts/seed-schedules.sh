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

echo "Schedules seeded."
echo ""
echo "NOTE: review-and-improve runs via idle-queue trigger in events.py"
echo "      (up to once per day when no other jobs are queued), not via cron."
echo ""
psql assistant -c "SELECT name, cron_expression, paused FROM schedules ORDER BY name;"
