#!/usr/bin/env bash
# scripts/healthcheck-all.sh — probe every project's healthcheck, update DB.
#
# Designed to run every 5 minutes via launchd (com.assistant.healthcheck-all).
# Fast (< 30s total for dozens of projects). No LLM involved.
#
# Usage:
#   bash scripts/healthcheck-all.sh
set -uo pipefail

# launchd gives us a minimal PATH; add Homebrew so `yq`, `curl`, `psql` resolve.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/healthcheck.log"

CHECKED=0
HEALTHY=0
FAILED=0

# Read from manifest files (source of truth, not DB)
while IFS= read -r manifest; do
    SLUG=$(yq '.slug' "$manifest")
    PORT=$(yq '.port // ""' "$manifest")
    HC=$(yq '.healthcheck // ""' "$manifest")
    TYPE=$(yq '.type' "$manifest")

    # Skip static projects (no healthcheck)
    [[ "$TYPE" == "static" ]] && continue
    # Skip if no healthcheck or port configured
    [[ -z "$HC" || -z "$PORT" ]] && continue

    CHECKED=$((CHECKED + 1))
    URL="http://localhost:$PORT$HC"

    if curl -sf --max-time 5 "$URL" > /dev/null 2>&1; then
        psql assistant -qc "UPDATE projects SET last_healthy_at = NOW() WHERE slug = '$SLUG';" > /dev/null 2>&1
        HEALTHY=$((HEALTHY + 1))
    else
        echo "$(date -u +%FT%TZ) FAIL $SLUG $URL" >> "$LOG"
        FAILED=$((FAILED + 1))
    fi

    # Also check sub-services if present
    NUM_SERVICES=$(yq '.services | length' "$manifest" 2>/dev/null || echo 0)
    if [[ "$NUM_SERVICES" -gt 0 ]]; then
        for i in $(seq 0 $((NUM_SERVICES - 1))); do
            SVC_NAME=$(yq ".services[$i].name" "$manifest")
            SVC_PORT=$(yq ".services[$i].port" "$manifest")
            SVC_HC=$(yq ".services[$i].healthcheck // \"\"" "$manifest")
            [[ -z "$SVC_HC" || -z "$SVC_PORT" ]] && continue

            CHECKED=$((CHECKED + 1))
            SVC_URL="http://localhost:$SVC_PORT$SVC_HC"

            if curl -sf --max-time 5 "$SVC_URL" > /dev/null 2>&1; then
                HEALTHY=$((HEALTHY + 1))
            else
                echo "$(date -u +%FT%TZ) FAIL $SLUG/$SVC_NAME $SVC_URL" >> "$LOG"
                FAILED=$((FAILED + 1))
            fi
        done
    fi
done < <(find "$PROJECT_DIR/projects" -name manifest.yml -not -path '*/.git/*' 2>/dev/null)

# ── Runner liveness backstop (dead-man's-switch gap, 2026-07-30 incident) ───
# This script runs from its own launchd timer, independent of the runner, so it
# can alert when every in-process alerter is dead. Alert condition (both):
#   1. Redis heartbeat `heartbeat:runner` (epoch seconds, TTL 15 min) missing
#      or older than 600s, AND
#   2. `launchctl list` shows no PID for com.assistant.runner.
# DM goes straight to the Telegram API with the bot token + FIRST id of
# TELEGRAM_ALLOWED_CHAT_IDS, both READ from this checkout's .env
# (TELEGRAM_ALLOWED_CHAT_IDS is auth config — never modified here).
# Rate-limited to one DM per 30 min via a state file under volumes/.
# Everything is guarded: this section must never block or fail the probes.
RUNNER_LABEL="com.assistant.runner"
HB_KEY="heartbeat:runner"
HB_STALE_SECONDS=600
ALERT_INTERVAL_SECONDS=1800
ALERT_STATE="$PROJECT_DIR/volumes/healthcheck-runner-alert.epoch"

check_runner_liveness() {
    local now hb age age_txt pid last_alert token chat_ids chat_id msg
    now=$(date +%s)

    # 1. Heartbeat age. Missing or non-numeric (pre-epoch runner) counts as
    #    stale — the launchctl AND-gate below keeps that from false-alarming.
    hb=$(redis-cli GET "$HB_KEY" 2>/dev/null || true)
    if [[ "$hb" =~ ^[0-9]+$ ]]; then
        age=$(( now - hb ))
        if (( age <= HB_STALE_SECONDS )); then
            return 0    # fresh heartbeat — runner alive
        fi
        age_txt="${age}s"
    else
        age_txt="missing"
    fi

    # 2. Only alert when launchd also has no live PID for the runner.
    pid=$(launchctl list 2>/dev/null | awk -v lbl="$RUNNER_LABEL" '$3 == lbl && $1 ~ /^[0-9]+$/ {print $1}' || true)
    if [[ -n "$pid" ]]; then
        echo "$(date -u +%FT%TZ) WARN runner heartbeat stale ($age_txt) but PID $pid present" >> "$LOG"
        return 0
    fi

    echo "$(date -u +%FT%TZ) FAIL runner heartbeat=$age_txt launchd=no-pid" >> "$LOG"

    # 3. Rate limit: at most one DM per ALERT_INTERVAL_SECONDS.
    last_alert=$(cat "$ALERT_STATE" 2>/dev/null || echo 0)
    [[ "$last_alert" =~ ^[0-9]+$ ]] || last_alert=0
    if (( now - last_alert < ALERT_INTERVAL_SECONDS )); then
        return 0
    fi

    # 4. READ Telegram creds from the checkout's .env (no export, no mutation).
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    if [[ -z "$token" || -z "$chat_id" ]]; then
        echo "$(date -u +%FT%TZ) WARN runner-down alert skipped: telegram creds missing in .env" >> "$LOG"
        return 0
    fi

    msg="🚨 Runner down on $(hostname -s): heartbeat $age_txt (limit ${HB_STALE_SECONDS}s) and launchd has no PID for $RUNNER_LABEL. Restart: launchctl kickstart -k gui/$(id -u)/$RUNNER_LABEL"
    if curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
            --data-urlencode "chat_id=${chat_id}" \
            --data-urlencode "text=${msg}" > /dev/null 2>&1; then
        echo "$now" > "$ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT runner-down DM sent to chat $chat_id" >> "$LOG"
    else
        echo "$(date -u +%FT%TZ) WARN runner-down DM failed (telegram unreachable?)" >> "$LOG"
    fi
    return 0
}

check_runner_liveness || true

# ── Swing trading watchdog (R18, spec 2026-08-27 v3 §6.2) ───────────────────
# OUT-OF-BAND by design: the scheduler cannot watchdog itself (08-17
# governor-dark incident). On market weekdays, if the swing vertical has no
# completed run inside its expected window, DM the owner — resting broker
# stops protect positions through loop death, but options lifecycle needs
# eyes. Fails SILENT-SAFE pre-deploy (no atlas .env / schema yet → WARN log).
SWING_ALERT_STATE="$PROJECT_DIR/volumes/healthcheck-swing-alert.epoch"
SWING_ALERT_INTERVAL=43200   # one DM per 12h

check_swing_freshness() {
    local now dow hour max_age atlas_env db_url last_ts last_epoch age token chat_ids chat_id msg last_alert
    now=$(date +%s); dow=$(date -u +%u); hour=$(date -u +%H)
    # weekends: nothing expected
    (( dow >= 6 )) && return 0
    # give the morning supervise run (13:40/14:40 UTC) time before judging
    (( 10#$hour < 16 )) && return 0
    # Mon looks back across the weekend (74h); Tue-Fri expect <26h
    if (( dow == 1 )); then max_age=266400; else max_age=93600; fi
    atlas_env="$PROJECT_DIR/projects/atlas/.env"
    db_url=$(grep -E '^DATABASE_URL=' "$atlas_env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    if [[ -z "$db_url" ]]; then
        echo "$(date -u +%FT%TZ) WARN swing watchdog: atlas .env/DATABASE_URL absent (pre-deploy?)" >> "$LOG"
        return 0
    fi
    last_ts=$(psql "$db_url" -X -q -t -A -c "SELECT extract(epoch from max(ts))::bigint FROM swing.runs;" 2>/dev/null || true)
    if [[ ! "$last_ts" =~ ^[0-9]+$ ]]; then
        echo "$(date -u +%FT%TZ) WARN swing watchdog: swing.runs unreadable/empty (pre-first-run?)" >> "$LOG"
        return 0
    fi
    age=$(( now - last_ts ))
    (( age <= max_age )) && return 0
    echo "$(date -u +%FT%TZ) FAIL swing watchdog: last swing.runs ${age}s old (limit ${max_age}s)" >> "$LOG"
    last_alert=$(cat "$SWING_ALERT_STATE" 2>/dev/null || echo 0)
    [[ "$last_alert" =~ ^[0-9]+$ ]] || last_alert=0
    (( now - last_alert < SWING_ALERT_INTERVAL )) && return 0
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    [[ -z "$token" || -z "$chat_id" ]] && return 0
    msg="🚨 Swing watchdog (R18): no completed swing run in $(( age / 3600 ))h on a market day. Resting broker stops protect stock lots; OPTION lifecycle needs eyes — check /trading/swing and the atlas-swing-* schedules."
    if curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
            --data-urlencode "chat_id=${chat_id}" \
            --data-urlencode "text=${msg}" > /dev/null 2>&1; then
        echo "$now" > "$SWING_ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT swing-watchdog DM sent" >> "$LOG"
    fi
    return 0
}

check_swing_freshness || true

# ── Deploy autopilot (continuous delivery, 2026-07-31) ──────────────────────
# Pushed-but-undeployed commits used to wait for a human to say "deploy".
# This zero-token check notices a pending origin/main range and dispatches a
# `deploy-director` job — the DIRECTOR (an LLM session) then does all judgment:
# preflight, risk class, in-flight-job safety, and the actual executor
# dispatch. This script only notices "there is something to deploy".
# Guards: DEPLOY_AUTOPILOT=0 in .env disables; range must be fast-forward and
# QUIET (tip ≥10 min old — never deploy mid-push-session); no deploy/director
# job already queued/running; one dispatch per 30 min. Never blocks probes.
DEPLOY_STATE="$PROJECT_DIR/volumes/healthcheck-deploy-dispatch.epoch"
DEPLOY_QUIET_SECONDS=600
DEPLOY_INTERVAL_SECONDS=1800

check_deploy_pending() {
    local now autopilot head remote tip_age last pending job_id active
    now=$(date +%s)

    autopilot=$(grep -E '^DEPLOY_AUTOPILOT=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    [[ "$autopilot" == "0" || "$autopilot" == "false" ]] && return 0

    git -C "$PROJECT_DIR" fetch origin main --quiet 2>/dev/null || return 0
    head=$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null) || return 0
    remote=$(git -C "$PROJECT_DIR" rev-parse origin/main 2>/dev/null) || return 0
    [[ "$head" == "$remote" ]] && return 0

    # fast-forward only — divergence is a human problem, log and stand down
    if ! git -C "$PROJECT_DIR" merge-base --is-ancestor "$head" "$remote" 2>/dev/null; then
        echo "$(date -u +%FT%TZ) WARN deploy-autopilot: HEAD/origin diverged — skipping" >> "$LOG"
        return 0
    fi

    # quiet window: don't chase a push session mid-flight
    tip_age=$(( now - $(git -C "$PROJECT_DIR" log -1 --format=%ct origin/main 2>/dev/null || echo "$now") ))
    (( tip_age < DEPLOY_QUIET_SECONDS )) && return 0

    # rate limit
    last=$(cat "$DEPLOY_STATE" 2>/dev/null || echo 0)
    [[ "$last" =~ ^[0-9]+$ ]] || last=0
    (( now - last < DEPLOY_INTERVAL_SECONDS )) && return 0

    # no deploy machinery already in flight
    active=$(psql assistant -tAc "SELECT count(*) FROM jobs WHERE status IN ('queued','running')
        AND (kind IN ('server-deploy','server_deploy','deploy-director','deploy_director')
             OR resolved_skill IN ('server-deploy','deploy-director'))" 2>/dev/null || echo 1)
    [[ "$active" =~ ^[0-9]+$ ]] || return 0
    (( active > 0 )) && return 0

    pending=$(git -C "$PROJECT_DIR" rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
    job_id=$(psql assistant -tAc "INSERT INTO jobs (id, kind, description, status, created_by, created_at)
        VALUES (gen_random_uuid(), 'deploy-director',
                'server — deploy autopilot: ' || '$pending' || ' pending commit(s) on origin/main (' || LEFT('$remote',8) || '); dispatched by healthcheck-all check_deploy_pending',
                'queued', 'deploy-autopilot', NOW()) RETURNING id;" 2>/dev/null | head -1 | tr -d ' ') || return 0
    [[ -n "$job_id" ]] || return 0
    if redis-cli rpush jobs:queue "$job_id" > /dev/null 2>&1; then
        echo "$now" > "$DEPLOY_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) AUTOPILOT dispatched deploy-director $job_id ($pending pending)" >> "$LOG"
    else
        psql assistant -qc "UPDATE jobs SET status='cancelled', error_message='autopilot RPUSH failed; row cancelled to avoid stranding' WHERE id='$job_id'::uuid;" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) WARN deploy-autopilot enqueue failed at RPUSH; job row cancelled" >> "$LOG"
    fi
    return 0
}

check_deploy_pending || true

# Summary (visible in healthcheck.out.log)
echo "$(date -u +%FT%TZ) checked=$CHECKED healthy=$HEALTHY failed=$FAILED"
