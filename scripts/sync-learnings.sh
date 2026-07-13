#!/usr/bin/env bash
# sync-learnings.sh — auto-publish runtime-written documentation to origin.
#
# The production checkout (~/Library/Application Support/ai-server) is a
# pull-only deploy target, but sessions legitimately WRITE docs at runtime
# (GOTCHAS.md, CHANGELOG.md, Troubleshooting entries). Before this script,
# those writes sat as uncommitted drift until a human "rescued" them by hand
# (see commits cbbdd02, 8cfbfc6, 60e1e5c).
#
# This script publishes doc-allowlisted working-tree changes to the
# `runtime-learnings` branch on origin WITHOUT touching HEAD, the local
# index, or the working tree — so it can run while the runner is live and
# never interferes with `git pull --ff-only` deploys. It uses git plumbing
# (temp index + commit-tree) instead of checkout/branch switching.
#
# The dev repo merges `runtime-learnings` into main like any other branch;
# the next `server-deploy` then reconciles the working tree (it stashes
# doc-drift around the pull — see skills/server-deploy/SKILL.md).
#
# Single-writer rule (CLAUDE.md): prod writes learnings, dev writes code.
#
# Usage:  bash scripts/sync-learnings.sh [--dry-run]
# Timer:  com.assistant.sync-learnings (hourly, installed by install-launchd.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BRANCH="runtime-learnings"
DRY_RUN="${1:-}"

cd "$PROJECT_DIR"

# Paths the runtime is ALLOWED to publish. Everything else (code, config)
# is drift that a human must look at — we report it but never publish it.
ALLOWLIST=(
    ".context/*.md"
    ".context/modules/*/*.md"
    ".context/modules/*/skills/*.md"
    "skills/*/*.md"
    "docs/Troubleshooting.md"
    "docs/TROUBLESHOOTING.md"
)

# ── Stray-commit safety net ─────────────────────────────────────────────
# A session that COMMITS on prod main (instead of leaving doc drift
# uncommitted) would break the next ff-only deploy. Detect commits ahead
# of origin/main and publish them to a rescue branch so nothing is ever
# stranded and deploys keep working after a reset. (Failure class of
# 2026-07-12, commit 7e22db9.)
git fetch origin main 2>/dev/null || true
ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
if [ "$ahead" -gt 0 ]; then
    RESCUE="runtime-rescue-auto"
    echo "sync-learnings: WARNING — $ahead unpushed commit(s) on prod main:"
    git log --oneline origin/main..HEAD | sed 's/^/  /'
    if [ "$DRY_RUN" != "--dry-run" ]; then
        git push origin "HEAD:refs/heads/$RESCUE" --force-with-lease 2>/dev/null \
          || git push origin "HEAD:refs/heads/$RESCUE" 2>/dev/null || true
        echo "sync-learnings: published to origin/$RESCUE — merge from dev, then"
        echo "  reset prod: git reset --hard origin/main (after the merge deploys)."
    fi
fi

# Collect changed tracked files matching the allowlist (modified only —
# untracked skill dirs come through new-skill's own commit path).
changed=$(git diff --name-only -- "${ALLOWLIST[@]}" || true)
if [ -z "$changed" ]; then
    echo "sync-learnings: nothing to publish."
    exit 0
fi

echo "sync-learnings: publishing runtime doc changes:"
echo "$changed" | sed 's/^/  /'

# Non-doc drift is a finding worth surfacing in the log (but not fatal).
other=$(git diff --name-only | grep -vxF "$changed" || true)
if [ -n "$other" ]; then
    echo "sync-learnings: WARNING — non-doc drift present (NOT published):"
    echo "$other" | sed 's/^/  /'
fi

if [ "$DRY_RUN" = "--dry-run" ]; then
    echo "sync-learnings: dry run — stopping before commit."
    exit 0
fi

git fetch origin "$BRANCH" 2>/dev/null || true

# Parent: continue the remote learnings branch if it exists, else fork from HEAD.
if git rev-parse --verify -q "origin/$BRANCH" >/dev/null; then
    PARENT=$(git rev-parse "origin/$BRANCH")
else
    PARENT=$(git rev-parse HEAD)
fi

# Build the commit in a TEMP index: start from the parent's tree so the
# learnings branch accumulates only doc changes (never reverts dev-side
# code it doesn't know about), then layer current doc files on top.
TMP_INDEX=$(mktemp -t sync-learnings-index)
trap 'rm -f "$TMP_INDEX"' EXIT

GIT_INDEX_FILE="$TMP_INDEX" git read-tree "$PARENT"
# shellcheck disable=SC2086
echo "$changed" | while IFS= read -r f; do
    GIT_INDEX_FILE="$TMP_INDEX" git update-index --add --replace -- "$f" 2>/dev/null || true
done
TREE=$(GIT_INDEX_FILE="$TMP_INDEX" git write-tree)

if [ "$TREE" = "$(git rev-parse "$PARENT^{tree}")" ]; then
    echo "sync-learnings: changes already published — nothing new."
    exit 0
fi

MSG="learn(runtime): auto-sync runtime learnings $(date -u +%Y-%m-%dT%H:%MZ)

Files:
$(echo "$changed" | sed 's/^/- /')

Published by scripts/sync-learnings.sh from the production checkout.
Merge into main from the dev repo; next server-deploy reconciles."

COMMIT=$(echo "$MSG" | git commit-tree "$TREE" -p "$PARENT")
git push origin "$COMMIT:refs/heads/$BRANCH"

echo "sync-learnings: pushed $COMMIT to origin/$BRANCH"
