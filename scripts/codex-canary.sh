#!/usr/bin/env bash
# scripts/codex-canary.sh — T10 live canary of the Codex executor
# (docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md §5 T10, §8).
#
# The ONE place that spawns the real `codex exec`. Everything else in the
# slice is fixture-driven. What it does:
#
#   1. Creates a throwaway seed repo + clone under CANARY_ROOT (a scratch
#      directory — refused under this repo, under the production checkout,
#      or under any volumes/).
#   2. Runs `src.runner.executors.codex_cli.main(["--canary", <clone>])` with
#      SERVER_ROOT pointed at <CANARY_ROOT>/fake-server-root and the dev
#      .env NOT loaded (PIPENV_DONT_LOAD_ENV=1), so the audit log and the
#      out-of-clone `-o` file land in the scratch area, never in prod.
#      The executor asserts: audit-kind order, TASK_COMPLETE marker, the
#      `-o` file outside the clone, one file written inside the clone and
#      nothing outside, no denied env name visible to the child, exit 0.
#   3. Runs `--gate-dry-run <clone> --base-sha <seed HEAD>`: the T5
#      Anthropic review of the clone's diff, verdict printed, no sync.
#
# Exit codes (from the executor): 0 all checks passed; 1 ran but a check
# failed; 2 did not run (rate-limited / login lapsed / no binary) — record
# it, do NOT retry in a loop; 3 refused location; 64 usage.
#
# Usage:
#   CANARY_ROOT=/path/to/scratch bash scripts/codex-canary.sh [--model gpt-6-luna]
#       [--timeout 600] [--no-gate] [--keep]
#
# Needs the owner's Codex login (`codex login status` → "Logged in using
# ChatGPT") in ~/.codex (or CODEX_HOME). Never starts the runner, bot or web.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PROD_ROOT="$HOME/Library/Application Support/ai-server"

MODEL="${CODEX_CANARY_MODEL:-gpt-6-luna}"
TIMEOUT="${CODEX_CANARY_TIMEOUT:-600}"
GATE=1
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model) MODEL="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --no-gate) GATE=0; shift ;;
        --keep) shift ;;  # the scratch area is never deleted anyway; accepted for symmetry
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 64 ;;
    esac
done

CANARY_ROOT="${CANARY_ROOT:-}"
if [[ -z "$CANARY_ROOT" ]]; then
    CANARY_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/codex-canary.XXXXXX")"
fi
mkdir -p "$CANARY_ROOT"
CANARY_ROOT="$(cd "$CANARY_ROOT" && pwd -P)"

refuse() { echo "refused: $*" >&2; exit 3; }
case "$CANARY_ROOT" in
    "$REPO_ROOT"|"$REPO_ROOT"/*) refuse "CANARY_ROOT is under this repo ($REPO_ROOT)" ;;
    "$PROD_ROOT"|"$PROD_ROOT"/*) refuse "CANARY_ROOT is under the production checkout" ;;
    */volumes/*|*/volumes) refuse "CANARY_ROOT is under a volumes/ directory" ;;
esac

SEED="$CANARY_ROOT/seed"
CLONE="$CANARY_ROOT/clone"
FAKE_ROOT="$CANARY_ROOT/fake-server-root"
RUN_ID="canary-$(date -u +%Y%m%dT%H%M%SZ)"
rm -rf "$SEED" "$CLONE"
mkdir -p "$FAKE_ROOT"

# A throwaway repo: the clone is what the executor gets as `-C`, the seed
# plays "canonical" only in that the clone has an origin and a base sha.
git init -q "$SEED"
printf 'codex canary seed\n' > "$SEED/README.md"
git -C "$SEED" -c user.name=canary -c user.email=canary@localhost add README.md
git -C "$SEED" -c user.name=canary -c user.email=canary@localhost commit -q -m "seed"
git clone -q "$SEED" "$CLONE"
BASE_SHA="$(git -C "$CLONE" rev-parse HEAD)"

echo "codex canary"
echo "  root:   $CANARY_ROOT"
echo "  clone:  $CLONE (base $BASE_SHA)"
echo "  model:  $MODEL   timeout: ${TIMEOUT}s   job: $RUN_ID"
echo "  audit:  $FAKE_ROOT/volumes/audit_log/$RUN_ID.jsonl"

# The dev .env points SERVER_ROOT at production; `pipenv run` would load it
# over the shell. Neither may happen here.
export PIPENV_DONT_LOAD_ENV=1
export SERVER_ROOT="$FAKE_ROOT"
cd "$REPO_ROOT"
# `python -m src.runner.executors.codex_cli` works too but runpy warns that
# the package __init__ already imported the module (it is then executed
# twice); importing `main` via -c (cwd on sys.path) avoids that.
ENTRY='import sys; from src.runner.executors.codex_cli import main; sys.exit(main(sys.argv[1:]))'

set +e
pipenv run python -c "$ENTRY" --canary "$CLONE" \
    --model "$MODEL" --timeout "$TIMEOUT" --job-id "$RUN_ID" \
    --report "$CANARY_ROOT/canary-report.json"
RC=$?
set -e

case "$RC" in
    0) echo "canary: PASS" ;;
    1) echo "canary: ran, checks FAILED (see $CANARY_ROOT/canary-report.json)" ;;
    2) echo "canary: DID NOT RUN (rate-limited / login lapsed / no binary) — recorded, not retried"
       exit 2 ;;
    *) echo "canary: exit $RC"; exit "$RC" ;;
esac

if [[ "$GATE" -eq 1 ]]; then
    echo "gate dry-run (Anthropic review of the clone diff; no sync)"
    set +e
    pipenv run python -c "$ENTRY" --gate-dry-run "$CLONE" \
        --base-sha "$BASE_SHA" --job-id "$RUN_ID" \
        --report "$CANARY_ROOT/gate-report.json"
    GRC=$?
    set -e
    [[ "$GRC" -eq 0 ]] || { echo "gate dry-run: exit $GRC"; RC=$GRC; }
fi

echo "reports: $CANARY_ROOT/canary-report.json $CANARY_ROOT/gate-report.json"
exit "$RC"
