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

# ── Interpreter for the notify CLI (A7, 2026-10-21) ─────────────────────────
# NEVER run python through the pipenv shim from a launchd script: pipenv is a
# ~/.pyenv shim that `bash -lc` cannot see (rc=127 — the schedule-monitor
# incident of 2026-09-14..10-05). Resolution order: the timer plist's VENV_PY
# (install-launchd.sh exports it) → `pipenv --venv` → pipenv's deterministic
# ~/.local/share/virtualenvs/<basename>-* location, preferring the venv whose
# pipenv-written `.project` file equals $PROJECT_DIR (whole-tier review
# 2026-10-22: on a host with both the dev and the prod checkout — same
# basename — the old first-match glob picked the DEV venv for prod's timers;
# a first-match fallback is kept only when no `.project` matches, and it is
# LOGGED) → none. An interpreter that cannot `import src.config` is treated as
# absent: the alerts then take the raw-curl path below and the alert-history
# row is simply not written. Both probes run in a SUBSHELL that cd's to the
# project root first: this script never cd's, and the editable install is
# inert under ~/Documents (the macOS hidden-.pth gotcha), so `import
# src.config` only resolves from there.
# Resolved LAZILY on the first notify_send (memoised): the 5-minute tick
# otherwise spawned the interpreter on every run with nothing to send, and a
# venv-less host logged the same WARN 288 times a day.
VENV_PY="${VENV_PY:-}"
_VENV_RESOLVED=0
resolve_venv_py() {   # sets VENV_PY; empty = no usable interpreter (curl path)
    (( _VENV_RESOLVED )) && return 0
    _VENV_RESOLVED=1
    local _venv _d _first=""
    if [[ -z "$VENV_PY" ]] && command -v pipenv >/dev/null 2>&1; then
        _venv="$(cd "$PROJECT_DIR" && pipenv --venv 2>/dev/null || true)"
        [[ -n "$_venv" && -x "$_venv/bin/python" ]] && VENV_PY="$_venv/bin/python"
    fi
    if [[ -z "$VENV_PY" ]]; then
        for _d in "$HOME/.local/share/virtualenvs/$(basename "$PROJECT_DIR")-"*; do
            [[ -x "$_d/bin/python" ]] || continue
            [[ -z "$_first" ]] && _first="$_d"
            if [[ "$(cat "$_d/.project" 2>/dev/null)" == "$PROJECT_DIR" ]]; then
                VENV_PY="$_d/bin/python"; break
            fi
        done
        if [[ -z "$VENV_PY" && -n "$_first" ]]; then
            VENV_PY="$_first/bin/python"
            echo "$(date -u +%FT%TZ) WARN no venv whose .project matches $PROJECT_DIR; using first match $_first (run install-launchd.sh timers-only to pin VENV_PY)" >> "$LOG"
        fi
    fi
    if [[ -n "$VENV_PY" ]] && ! (cd "$PROJECT_DIR" && "$VENV_PY" -c 'import src.config') >/dev/null 2>&1; then
        echo "$(date -u +%FT%TZ) WARN venv python unusable ($VENV_PY); alerts fall back to curl" >> "$LOG"
        VENV_PY=""
    fi
    [[ -z "$VENV_PY" ]] && echo "$(date -u +%FT%TZ) WARN no project venv python found; alerts fall back to curl (no alert-history row)" >> "$LOG"
    return 0
}

# Owner DM path: the notifications outbox CLI first (direct Telegram HTTP +
# a `notifications` row = the alert history), the raw curl at each call site
# as the fallback when the CLI itself cannot run or did not deliver. Both are
# out-of-band: neither depends on the bot or the runner being alive, and the
# CLI exits non-zero whenever the DM was not delivered, so `notify_send … ||
# curl` never drops an alert. Never reads `NOTIFY_OUTBOX` (the switch is the
# bot's, D-P1-10).
notify_send() {   # $1 = kind  $2 = text ; returns 0 only when the DM was delivered
    resolve_venv_py
    [[ -n "$VENV_PY" ]] || return 1
    (cd "$PROJECT_DIR" && "$VENV_PY" -m src.notify send --kind "$1" --severity critical \
        --text "$2" >> "$LOG" 2>&1)
}

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
# DM goes through `notify_send` (the outbox CLI, A7) first and falls back to
# the Telegram API directly with the bot token + FIRST id of
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
    if notify_send ops_alert "$msg"; then
        echo "$now" > "$ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT runner-down sent via notify" >> "$LOG"
    elif curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
            --data-urlencode "chat_id=${chat_id}" \
            --data-urlencode "text=${msg}" > /dev/null 2>&1; then
        echo "$now" > "$ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT runner-down DM sent to chat $chat_id (curl fallback)" >> "$LOG"
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
    if notify_send ops_alert "$msg"; then
        echo "$now" > "$SWING_ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT swing-watchdog sent via notify" >> "$LOG"
    elif curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
            --data-urlencode "chat_id=${chat_id}" \
            --data-urlencode "text=${msg}" > /dev/null 2>&1; then
        echo "$now" > "$SWING_ALERT_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) ALERT swing-watchdog DM sent (curl fallback)" >> "$LOG"
    fi
    return 0
}

check_swing_freshness || true

# ── Deploy-in-flight probe (shared by both autopilots, 2026-11-21) ──────────
# Returns 0 ("busy") when ANY deploy machinery is queued or running — server
# or project — or when the answer is unknown (psql down = stand down). The
# `resolved_skill` arm catches deploys that arrived as kind='task' via
# `/task redeploy …` routing. Serializing every deploy means a server deploy
# (which restarts the runner) never lands on top of a project deploy, and two
# project deploys never race each other.
deploy_in_flight() {   # 0 = busy or unknown, 1 = idle
    local active
    active=$(psql assistant -tAc "SELECT count(*) FROM jobs WHERE status IN ('queued','running')
        AND (kind IN ('server-deploy','server_deploy','deploy-director','deploy_director')
             OR resolved_skill IN ('server-deploy','deploy-director')
             OR kind LIKE '%\_redeploy' OR kind LIKE '%-redeploy'
             OR resolved_skill LIKE '%-redeploy')" 2>/dev/null || echo x)
    active=$(printf '%s' "$active" | tr -d '[:space:]')
    [[ "$active" =~ ^[0-9]+$ ]] || return 0
    (( active > 0 ))
}

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

    # no deploy machinery already in flight (server OR project — a server
    # deploy restarts the runner, which would kill a project deploy mid-run)
    deploy_in_flight && return 0

    pending=$(git -C "$PROJECT_DIR" rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
    job_id=$(psql assistant -tAc "INSERT INTO jobs (id, kind, description, status, created_by, created_at)
        VALUES (gen_random_uuid(), 'deploy-director',
                'server — deploy autopilot: ' || '$pending' || ' pending commit(s) on origin/main (' || LEFT('$remote',8) || '); dispatched by healthcheck-all check_deploy_pending',
                'queued', 'deploy-autopilot', NOW()) RETURNING id;" 2>/dev/null | head -1 | tr -d ' ') || return 0
    [[ -n "$job_id" ]] || return 0
    # LPUSH = front of the queue (2026-11-20): a deploy must not wait behind a
    # reboot catch-up burst or a sweep fan-out (11-17: 6 h behind 77 jobs).
    if redis-cli lpush jobs:queue "$job_id" > /dev/null 2>&1; then
        echo "$now" > "$DEPLOY_STATE" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) AUTOPILOT dispatched deploy-director $job_id ($pending pending)" >> "$LOG"
    else
        psql assistant -qc "UPDATE jobs SET status='cancelled', error_message='autopilot LPUSH failed; row cancelled to avoid stranding' WHERE id='$job_id'::uuid;" 2>/dev/null || true
        echo "$(date -u +%FT%TZ) WARN deploy-autopilot enqueue failed at LPUSH; job row cancelled" >> "$LOG"
    fi
    return 0
}

check_deploy_pending || true

# ── Project deploy autopilot (2026-11-21) ───────────────────────────────────
# The server autopilot above watches only this checkout. This one watches every
# project whose manifest carries a gated-auto dev-repo delivery contract and,
# when a new commit lands on that project's delivery branch, dispatches the
# project's OWN deploy executor (`delivery.deploy.skill`: atlas-redeploy, or
# project-redeploy by default) straight onto the front of the queue. Noticing
# costs zero tokens; the executor (a low-effort session that escalates only on
# failure) does pull → migrate → gates → build → restart → healthcheck, and a
# red test/build gate leaves the old code serving. No deploy-director hop: the
# preflight it adds for projects (in-flight guard, divergence, marker) is done
# here, and the follow-up below is the verify step.
#
#   eligible   topology dev-repo + runtime_clone pull-only + deployable not
#              false + autonomy gated-auto + ≥1 service + the executor skill
#              exists. In-place, human-approval, manual-only and content
#              projects are left exactly as they are.
#   once/tip   volumes/state/autodeploy-<slug> = "<tip> <job_id|-> <0|1>".
#              A tip is tried once; a red deploy waits for the NEXT commit
#              (no token loop on a broken gate).
#   docs       a new range that touches only *.md files dispatches nothing —
#              the loops' ledger commits — and the next code change ships
#              them, because executors deploy from the deployed-sha marker.
#              DEPLOY_AUTOPILOT_INCLUDE_DOCS=1 deploys them too.
#   guards     tip ≥ DEPLOY_QUIET_SECONDS old; fast-forward only (divergence
#              = one owner alert, no dispatch); nothing deploy-shaped in
#              flight anywhere (deploy_in_flight); one dispatch per tick.
#   follow-up  once no deploy is in flight, the attempt is judged by the
#              executor's marker: at/after the tip = shipped (logged);
#              otherwise ONE owner alert naming the job.
#   switches   .env DEPLOY_AUTOPILOT=0 stops both autopilots;
#              DEPLOY_AUTOPILOT_PROJECTS=0 stops this one;
#              DEPLOY_AUTOPILOT_SKIP=slug,slug skips those projects.
PROJ_STATE_DIR="$PROJECT_DIR/volumes/state"

env_value() {   # $1 = NAME → its value from this checkout's .env (read-only)
    grep -E "^$1=" "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true
}

alert_owner() {   # $1 = text; 0 = delivered (notify first, curl fallback)
    local token chat_ids chat_id
    token=$(env_value TELEGRAM_BOT_TOKEN)
    chat_ids=$(env_value TELEGRAM_ALLOWED_CHAT_IDS)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    if notify_send ops_alert "$1"; then
        echo "$(date -u +%FT%TZ) ALERT project-deploy sent via notify" >> "$LOG"
        return 0
    elif [[ -z "$token" || -z "$chat_id" ]]; then
        echo "$(date -u +%FT%TZ) WARN project-deploy alert skipped: telegram creds missing in .env" >> "$LOG"
        return 1
    elif curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
            --data-urlencode "chat_id=${chat_id}" \
            --data-urlencode "text=$1" > /dev/null 2>&1; then
        echo "$(date -u +%FT%TZ) ALERT project-deploy DM sent (curl fallback)" >> "$LOG"
        return 0
    fi
    echo "$(date -u +%FT%TZ) WARN project-deploy DM failed (telegram unreachable?)" >> "$LOG"
    return 1
}

# Prints "<kind> <branch>" when projects/<slug>/manifest.yml is an eligible
# autopilot target, nothing otherwise. `yq -r` works with both the Go (brew)
# and the Python yq. `deployable` is read raw: `//` treats false as missing.
project_deploy_target() {   # $1 = manifest path
    local m="$1" topo clone deployable autonomy nsvc skill branch
    topo=$(yq -r '.delivery.topology // ""' "$m" 2>/dev/null) || return 0
    [[ "$topo" == "dev-repo" ]] || return 0
    clone=$(yq -r '.delivery.runtime_clone // ""' "$m" 2>/dev/null)
    [[ "$clone" == "pull-only" ]] || return 0
    deployable=$(yq -r '.delivery.deployable' "$m" 2>/dev/null)
    [[ "$deployable" == "false" ]] && return 0
    autonomy=$(yq -r '.delivery.deploy.autonomy // "gated-auto"' "$m" 2>/dev/null)
    [[ "$autonomy" == "gated-auto" ]] || return 0
    nsvc=$(yq -r '.delivery.deploy.services // [] | length' "$m" 2>/dev/null)
    [[ "$nsvc" =~ ^[0-9]+$ ]] && (( nsvc > 0 )) || return 0
    skill=$(yq -r '.delivery.deploy.skill // ""' "$m" 2>/dev/null)
    [[ -z "$skill" || "$skill" == "null" ]] && skill="project-redeploy"   # = DeployPolicy default
    [[ "$skill" =~ ^[a-z0-9][a-z0-9-]*$ && -f "$PROJECT_DIR/skills/$skill/SKILL.md" ]] || return 0
    branch=$(yq -r '.delivery.branch // "main"' "$m" 2>/dev/null)
    [[ "$branch" =~ ^[A-Za-z0-9._/-]+$ ]] || return 0
    printf '%s %s\n' "${skill//-/_}" "$branch"
}

# True (0) when every path changed in $2..$3 of repo $1 is a *.md file.
range_is_docs_only() {
    local files
    files=$(git -C "$1" diff --name-only "$2" "$3" 2>/dev/null) || return 1
    [[ -n "$files" ]] || return 0
    ! printf '%s\n' "$files" | grep -qvE '\.md$'
}

# Judge the last dispatched attempt for <slug> once no deploy is in flight.
project_deploy_followup() {   # $1 slug  $2 runtime clone
    local slug="$1" P="$2" state st_tip st_job st_rep marker status
    state="$PROJ_STATE_DIR/autodeploy-$slug"
    [[ -s "$state" ]] || return 0
    read -r st_tip st_job st_rep < "$state" || return 0
    [[ "$st_rep" == "0" && "$st_job" =~ ^[0-9a-f-]{36}$ ]] || return 0
    deploy_in_flight && return 0
    marker=$(cat "$PROJ_STATE_DIR/deployed-sha-$slug" 2>/dev/null || true)
    if [[ -n "$marker" ]] && { [[ "$marker" == "$st_tip" ]] ||
            git -C "$P" merge-base --is-ancestor "$st_tip" "$marker" 2>/dev/null; }; then
        echo "$(date -u +%FT%TZ) AUTOPILOT $slug deployed ${st_tip:0:8} (job ${st_job:0:8})" >> "$LOG"
    else
        status=$(psql assistant -tAc "SELECT status FROM jobs WHERE id='$st_job'::uuid;" 2>/dev/null | tr -d '[:space:]')
        echo "$(date -u +%FT%TZ) FAIL project-deploy $slug ${st_tip:0:8} not shipped (job ${st_job:0:8} ${status:-unknown})" >> "$LOG"
        alert_owner "⚠️ Auto-deploy of $slug ${st_tip:0:8} didn't finish green on $(hostname -s) (job ${st_job:0:8}, ${status:-status unknown}). If a test or build check failed, the old version is still serving. The job summary says what happened; the next commit to the branch triggers a fresh attempt." || true
    fi
    printf '%s %s 1\n' "$st_tip" "$st_job" > "$state" 2>/dev/null || true
}

check_project_deploys() {
    local now flag skip manifest slug P target kind branch state st_tip st_job st_rep
    local head tip marker deployed base tip_age pending job_id
    now=$(date +%s)
    flag=$(env_value DEPLOY_AUTOPILOT)
    [[ "$flag" == "0" || "$flag" == "false" ]] && return 0
    flag=$(env_value DEPLOY_AUTOPILOT_PROJECTS)
    [[ "$flag" == "0" || "$flag" == "false" ]] && return 0
    skip=",$(env_value DEPLOY_AUTOPILOT_SKIP | tr -d '[:space:]'),"
    mkdir -p "$PROJ_STATE_DIR" 2>/dev/null || true

    for manifest in "$PROJECT_DIR"/projects/*/manifest.yml; do
        [[ -f "$manifest" ]] || continue
        P=$(dirname "$manifest")
        slug=$(basename "$P")            # the executor's slug = directory name
        [[ "$slug" =~ ^[a-z0-9][a-z0-9-]*$ ]] || continue
        [[ "$skip" == *",$slug,"* ]] && continue
        target=$(project_deploy_target "$manifest")
        [[ -n "$target" ]] || continue
        kind=${target% *}; branch=${target#* }
        git -C "$P" rev-parse --git-dir > /dev/null 2>&1 || continue

        project_deploy_followup "$slug" "$P"

        GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10" \
            git -C "$P" fetch origin "$branch" --quiet 2>/dev/null || {
            echo "$(date -u +%FT%TZ) WARN project-deploy $slug: fetch origin $branch failed" >> "$LOG"
            continue; }
        tip=$(git -C "$P" rev-parse "origin/$branch" 2>/dev/null) || continue
        head=$(git -C "$P" rev-parse HEAD 2>/dev/null) || continue
        marker=$(cat "$PROJ_STATE_DIR/deployed-sha-$slug" 2>/dev/null || true)
        deployed=$head
        if [[ -n "$marker" ]] && git -C "$P" cat-file -e "$marker^{commit}" 2>/dev/null; then
            deployed=$marker
        fi
        # already shipped (marker at or past the tip)
        [[ "$tip" == "$deployed" ]] && continue
        git -C "$P" merge-base --is-ancestor "$tip" "$deployed" 2>/dev/null && continue

        st_tip="" st_job="" st_rep=""
        state="$PROJ_STATE_DIR/autodeploy-$slug"
        [[ -s "$state" ]] && read -r st_tip st_job st_rep < "$state"
        [[ "$st_tip" == "$tip" ]] && continue          # this tip was already tried

        # fast-forward only — runtime-born commits are a human problem. One
        # DM per divergent HEAD (not per new tip: atlas's loops push several
        # times a day), then silence until someone reconciles the clone.
        if ! git -C "$P" merge-base --is-ancestor "$head" "$tip" 2>/dev/null; then
            if [[ "$(cat "$state.diverged" 2>/dev/null)" != "$head" ]]; then
                echo "$(date -u +%FT%TZ) WARN project-deploy $slug: runtime clone diverged from origin/$branch — skipping until reconciled" >> "$LOG"
                alert_owner "⚠️ Can't auto-deploy $slug: its runtime copy on $(hostname -s) has commits that aren't on GitHub ($(git -C "$P" rev-list --count "$tip..$head" 2>/dev/null || echo '?') ahead), so a fast-forward pull would refuse. A person needs to reconcile it; auto-deploys of $slug are paused until then." || true
                printf '%s\n' "$head" > "$state.diverged" 2>/dev/null || true
            fi
            continue
        fi
        rm -f "$state.diverged" 2>/dev/null || true

        # what's new since the last attempt (or since the last deploy)
        base=$deployed
        if [[ -n "$st_tip" ]] && git -C "$P" merge-base --is-ancestor "$st_tip" "$tip" 2>/dev/null &&
                git -C "$P" merge-base --is-ancestor "$deployed" "$st_tip" 2>/dev/null; then
            base=$st_tip
        fi
        if [[ "$(env_value DEPLOY_AUTOPILOT_INCLUDE_DOCS)" != "1" ]] && range_is_docs_only "$P" "$base" "$tip"; then
            continue
        fi

        tip_age=$(( now - $(git -C "$P" log -1 --format=%ct "$tip" 2>/dev/null || echo "$now") ))
        (( tip_age < DEPLOY_QUIET_SECONDS )) && continue
        deploy_in_flight && return 0

        pending=$(git -C "$P" rev-list --count "$deployed..$tip" 2>/dev/null || echo "?")
        job_id=$(psql assistant -tAc "INSERT INTO jobs (id, kind, description, payload, status, created_by, created_at)
            VALUES (gen_random_uuid(), '$kind',
                    '$slug — deploy autopilot: $pending undeployed commit(s), origin/$branch at ' || LEFT('$tip',8) || '; dispatched by healthcheck-all check_project_deploys',
                    '{\"project_slug\": \"$slug\"}'::json,
                    'queued', 'deploy-autopilot', NOW()) RETURNING id;" 2>/dev/null | head -1 | tr -d ' ') || return 0
        [[ -n "$job_id" ]] || return 0
        if redis-cli lpush jobs:queue "$job_id" > /dev/null 2>&1; then
            printf '%s %s 0\n' "$tip" "$job_id" > "$state" 2>/dev/null || true
            echo "$(date -u +%FT%TZ) AUTOPILOT dispatched $kind $job_id for $slug ($pending pending, tip ${tip:0:8})" >> "$LOG"
        else
            psql assistant -qc "UPDATE jobs SET status='cancelled', error_message='autopilot LPUSH failed; row cancelled to avoid stranding' WHERE id='$job_id'::uuid;" 2>/dev/null || true
            echo "$(date -u +%FT%TZ) WARN project-deploy $slug enqueue failed at LPUSH; job row cancelled" >> "$LOG"
        fi
        return 0        # one dispatch per tick; the rest wait behind it
    done
    return 0
}

check_project_deploys || true

# Summary (visible in healthcheck.out.log)
echo "$(date -u +%FT%TZ) checked=$CHECKED healthy=$HEALTHY failed=$FAILED"
