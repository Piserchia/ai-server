#!/usr/bin/env bash
# install-prod-hooks.sh — git hooks for the PRODUCTION checkout only.
#
# Enforces the single-writer topology at the git layer instead of by
# convention: commits on `main` in production are blocked with guidance.
# Runtime doc learnings must stay uncommitted (the hourly sync-learnings
# timer publishes them); server code is born in the dev repo.
#
# Break-glass: the god lane (phone-initiated server fixes) may bypass with
#   AI_SERVER_ALLOW_MAIN_COMMIT=1 git commit ...
# under one condition, spelled out in skills/god/SKILL.md: PUSH IN THE SAME
# SESSION. An unpushed prod commit is the failure class that broke deploys
# on 2026-07-12 (commit 7e22db9).
#
# Safety: the hook only arms itself inside "Application Support/ai-server"
# so a copied repo (or the dev checkout) is never blocked.
#
# Installed by: server-deploy skill (every deploy re-installs — hooks are
# untracked, so this keeps them self-healing) and bootstrap.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HOOK="$PROJECT_DIR/.git/hooks/pre-commit"

case "$PROJECT_DIR" in
  *"Application Support/ai-server"*) ;;
  *)
    echo "install-prod-hooks: not the production checkout ($PROJECT_DIR) — skipping."
    exit 0
    ;;
esac

cat > "$HOOK" << 'HOOKEOF'
#!/usr/bin/env bash
# Production pre-commit guard (installed by scripts/install-prod-hooks.sh).
# The production checkout is a pull-only deploy target (CLAUDE.md
# § Single-writer topology).

# Only guard the production path — a copied/moved repo is not blocked.
case "$PWD" in
  *"Application Support/ai-server"*) ;;
  *) exit 0 ;;
esac

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ "$branch" = "main" ] && [ "${AI_SERVER_ALLOW_MAIN_COMMIT:-}" != "1" ]; then
    cat >&2 << 'MSG'
✗ BLOCKED: commits on main are not allowed in the production checkout.

  Why: production is a pull-only deploy target. An unpushed commit here
  makes every future `git pull --ff-only` deploy refuse (single-writer
  rule, CLAUDE.md). This exact failure broke deploys on 2026-07-12.

  What to do instead:
  - Runtime doc learning (GOTCHAS/CHANGELOG/Troubleshooting)?
    → Just leave the file modified. Do NOT commit. The hourly
      sync-learnings timer publishes it to origin/runtime-learnings.
  - Server code fix?
    → Make it in the dev repo (~/Documents/repos/ai-server) and deploy,
      OR (god break-glass only): bypass with
        AI_SERVER_ALLOW_MAIN_COMMIT=1 git commit ...
      and you MUST `git push origin main` in the same session.
MSG
    exit 1
fi
exit 0
HOOKEOF
chmod +x "$HOOK"
echo "install-prod-hooks: pre-commit guard installed at $HOOK"
