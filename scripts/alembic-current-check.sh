#!/usr/bin/env bash
# scripts/alembic-current-check.sh — owner-run diagnostic for the spec §9
# rollback rule (E8): the DB's alembic_version must name a revision that has a
# script on disk, or the next `alembic upgrade head` fails "Can't locate
# revision" mid-deploy. Exit 0 ok · 1 mismatch · 2 cannot determine.
#
# RUN BY HAND after any migration revert (runbook). NOT wired into
# skills/server-deploy/SKILL.md (a protected path): what protects the deploy is
# tests/test_migrations.py (the manifest tests inside the pytest gate
# server-deploy already runs) plus the runner's own startup check
# (`main._check_alembic_history`, which refuses to start on a gap).
# Never pipenv (bash -lc under launchd has no pipenv on PATH — rc=127).
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR" || exit 2

# Resolve the project venv's Python directly (§4; same order as
# scripts/schedule-monitor.sh): VENV_PY if exported → `pipenv --venv` → fail.
VENV_PY="${VENV_PY:-}"
if [[ -z "$VENV_PY" ]]; then
    PIPENV_VENV=""
    if command -v pipenv >/dev/null 2>&1; then
        PIPENV_VENV="$(pipenv --venv 2>/dev/null || true)"
    fi
    if [[ -n "$PIPENV_VENV" && -x "$PIPENV_VENV/bin/python" ]]; then
        VENV_PY="$PIPENV_VENV/bin/python"
    fi
fi
if [[ -z "$VENV_PY" ]] || ! "$VENV_PY" -c 'import src.config, alembic' 2>/dev/null; then
    echo "alembic-current-check: no usable interpreter (VENV_PY='${VENV_PY:-}')" >&2
    exit 2
fi

# `alembic current` prints e.g. "008 (head)"; empty on a DB with no alembic_version row.
current=$("$VENV_PY" -m alembic current 2>/dev/null | awk 'NF {print $1; exit}')
if [[ -z "$current" ]]; then
    echo "alembic-current-check: could not read alembic_version (empty DB? alembic env broken?)" >&2
    exit 2
fi
if ls "$PROJECT_DIR"/alembic/versions/"${current}"_*.py >/dev/null 2>&1; then
    echo "alembic-current-check: OK alembic_version=$current has a script on disk"
    exit 0
fi
echo "alembic-current-check: FAIL alembic_version=$current has NO script under alembic/versions/ — a revert removed a migration file. Restore the file; only if the migration itself must go, run: \"$VENV_PY\" -m alembic downgrade -1 BEFORE removing it (spec §9 rollback rule)." >&2
exit 1
