#!/usr/bin/env bash
# scripts/cost-reconcile-run.sh — weekly launchd wrapper for scripts/cost-reconcile.py
# (Observability Phase 1 B4; spec §2.8/§9; timer `com.assistant.cost-reconcile`,
# Monday 07:30 local, installed by scripts/install-launchd.sh — D-P1-8: a timer,
# not a schedule row).
#
# Runs the two-window list-price ledger (trailing 30 d + 7 d, the per-kind step,
# computed-vs-SDK, the weekly allowance), the --db leg against
# jobs.cost_usd_list / jobs.sdk_cost_usd, and re-seeds the lane budgets
# (volumes/telemetry/lane_budget_seed.json — printed, never applied: the
# owner pastes it into LANE_WEEKLY_BUDGET_JSON at Phase 3). Output appends to
# volumes/logs/cost-reconcile.log. A non-zero exit is DM'd to the owner:
# rc=1 is the 5-minute cache-write (usage-credits) signature — RESERVED, the
# CLI never exits 1 for anything else; rc=3 is "the run itself failed" (the
# --db leg could not reach Postgres, a ledger-parse crash: a `... failed:`
# line + traceback in the log); rc=2 = no audit dir. Anything but 1 is DM'd
# as "the weekly run failed — read the log". Deterministic, no LLM,
# out-of-band.
#
# Usage: bash scripts/cost-reconcile-run.sh
set -uo pipefail
# launchd gives this timer a minimal PATH — add the usual bin dirs so pipenv
# (if any), brew tools and curl resolve.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG="$PROJECT_DIR/volumes/logs/cost-reconcile.log"
mkdir -p "$(dirname "$LOG")"

# cd FIRST: `pipenv --venv` finds the Pipfile by cwd, and the editable install
# is inert under ~/Documents (macOS hidden-.pth gotcha), so `import src.config`
# only resolves from the project root.
cd "$PROJECT_DIR"

# Resolve the project venv's Python directly — NEVER through the pipenv shim
# (launchd's `bash -lc` cannot see ~/.pyenv/shims: rc=127, the 2026-09-14..10-05
# schedule-monitor incident). Order (plan §4): the timer plist's VENV_PY if
# exported → `pipenv --venv` → pipenv's deterministic
# ~/.local/share/virtualenvs/<basename>-* location → a LOGGED failure, never a
# silent fallback.
VENV_PY="${VENV_PY:-}"
if [[ -z "$VENV_PY" ]]; then
    PIPENV_VENV=""
    if command -v pipenv >/dev/null 2>&1; then
        PIPENV_VENV="$(pipenv --venv 2>/dev/null || true)"
    fi
    if [[ -z "$PIPENV_VENV" || ! -x "$PIPENV_VENV/bin/python" ]]; then
        # Prefer the venv whose pipenv-written `.project` equals $PROJECT_DIR:
        # on a host with both the dev and the prod checkout (same basename)
        # the first match is the DEV venv (whole-tier review 2026-10-22).
        # First-match is kept only as a LOGGED fallback.
        base="$(basename "$PROJECT_DIR")"
        first=""
        for d in "$HOME/.local/share/virtualenvs/${base}-"*; do
            [[ -x "$d/bin/python" ]] || continue
            [[ -z "$first" ]] && first="$d"
            if [[ "$(cat "$d/.project" 2>/dev/null)" == "$PROJECT_DIR" ]]; then PIPENV_VENV="$d"; break; fi
        done
        if [[ -z "$PIPENV_VENV" && -n "$first" ]]; then
            PIPENV_VENV="$first"
            echo "$(date -u +%FT%TZ) WARN no venv whose .project matches $PROJECT_DIR; using first match $first (run install-launchd.sh timers-only to pin VENV_PY)" >> "$LOG"
        fi
    fi
    VENV_PY="${PIPENV_VENV:+$PIPENV_VENV/bin/python}"
fi
if [[ -n "$VENV_PY" && -x "$VENV_PY" ]] && ! "$VENV_PY" -c 'import src.config' >/dev/null 2>&1; then
    echo "$(date -u +%FT%TZ) WARN venv python unusable ($VENV_PY): cannot import src.config from $PROJECT_DIR" >> "$LOG"
    VENV_PY=""
fi

# Owner DM: the notifications outbox CLI first (direct Telegram HTTP + a
# `notifications` row = the alert history), the raw curl as the fallback when
# the CLI cannot run or did not deliver. Out-of-band either way — no dependency
# on the bot or the runner. Never reads `NOTIFY_OUTBOX` (the switch is the
# bot's, D-P1-10). Always returns 0: an undeliverable alert is a WARN line,
# never the wrapper's own failure.
send_alert() {
    local msg="$1" token chat_ids chat_id
    if [[ -n "$VENV_PY" ]] && (cd "$PROJECT_DIR" && "$VENV_PY" -m src.notify send --kind ops_alert --severity warn \
            --text "$msg" >> "$LOG" 2>&1); then
        echo "$(date -u +%FT%TZ) ALERT sent via notify" >> "$LOG"; return 0
    fi
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_ids=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    chat_id=$(printf '%s' "$chat_ids" | cut -d, -f1 | tr -d '[:space:]')
    [[ -z "$token" || -z "$chat_id" ]] && { echo "$(date -u +%FT%TZ) WARN DM skipped: creds missing" >> "$LOG"; return 0; }
    curl -sf --max-time 10 "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat_id}" \
        --data-urlencode "text=${msg}" > /dev/null 2>&1 \
        && echo "$(date -u +%FT%TZ) ALERT DM sent (curl fallback)" >> "$LOG" \
        || echo "$(date -u +%FT%TZ) WARN DM failed" >> "$LOG"
    return 0
}

if [[ -z "$VENV_PY" ]]; then
    echo "$(date -u +%FT%TZ) FATAL cost-reconcile cannot locate a usable project venv python (searched: VENV_PY, PATH pipenv, ~/.local/share/virtualenvs/$(basename "$PROJECT_DIR")-* preferring .project == $PROJECT_DIR)" >> "$LOG"
    send_alert "cost-reconcile: weekly run did NOT run — no usable project venv python (see volumes/logs/cost-reconcile.log)"
    exit 0
fi

echo "$(date -u +%FT%TZ) run start" >> "$LOG"
"$VENV_PY" scripts/cost-reconcile.py --windows 30,7 --db --seed-lane-budgets >> "$LOG" 2>&1
rc=$?
echo "$(date -u +%FT%TZ) run rc=$rc" >> "$LOG"

# rc=1 is the CLI's reserved credits-signature code (a DB outage is rc=3, a
# missing audit dir rc=2 — never 1), so this branch is the billing DM only.
if (( rc == 1 )); then
    send_alert "cost-reconcile: 5-minute cache writes present — possible usage-credit overflow (spec §2.8). Check claude.ai billing before anything else. Details: volumes/logs/cost-reconcile.log"
elif (( rc != 0 )); then
    send_alert "cost-reconcile: weekly run failed (rc=$rc; 3 = the run itself failed, e.g. the --db leg could not reach Postgres) — see volumes/logs/cost-reconcile.log"
fi
exit 0
