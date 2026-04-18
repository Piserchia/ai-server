#!/usr/bin/env bash
# bootstrap.sh — first-time server setup.
# Run once after cloning the repo. Idempotent; safe to re-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ANTHROPIC_API_KEY must never be set for this server; it would flip the SDK to API billing.
unset ANTHROPIC_API_KEY || true

echo "=== Assistant bootstrap ==="
echo "  Project: $PROJECT_DIR"
echo ""

# ── Dependency checks ───────────────────────────────────────────────────────
need() {
    if ! command -v "$1" &>/dev/null; then
        echo "✗ Missing: $1"
        echo "  Install: $2"
        return 1
    fi
    echo "✓ $1"
}

echo "Checking dependencies..."
missing=0
need brew "https://brew.sh" || missing=1
need python3 "brew install python@3.12" || missing=1
need pipenv "brew install pipenv" || missing=1
need psql "brew install postgresql@15" || missing=1
need redis-cli "brew install redis" || missing=1
need gh "brew install gh" || missing=1
need claude "curl -fsSL https://claude.ai/install.sh | bash" || missing=1

if [ $missing -ne 0 ]; then
    echo ""
    echo "Install the missing tools above, then rerun bootstrap.sh."
    exit 1
fi
echo ""

# ── .env ────────────────────────────────────────────────────────────────────
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Creating .env from .env.example (edit before first run)..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  Edit $PROJECT_DIR/.env and fill in TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_IDS, POSTGRES_DSN, WEB_AUTH_TOKEN"
    echo ""
fi

# ── Claude Code CLI auth ────────────────────────────────────────────────────
echo "Checking Claude Code CLI auth..."
if ! claude --version &>/dev/null; then
    echo "✗ claude CLI not working. Reinstall."
    exit 1
fi
# We can't reliably probe login status without making a real request.
# Prompt the user:
echo "  If this is your first run, execute: claude login"
echo "  (Skip if already logged in.)"
echo ""

# ── Python deps ─────────────────────────────────────────────────────────────
echo "Installing Python dependencies (pipenv)..."
cd "$PROJECT_DIR"
pipenv install --dev
echo ""

# ── Infrastructure services ─────────────────────────────────────────────────
echo "Starting infrastructure services..."
if ! brew services list 2>/dev/null | grep -q "postgresql.*started"; then
    brew services start postgresql@15 2>/dev/null || brew services start postgresql 2>/dev/null || true
fi
if ! brew services list 2>/dev/null | grep -q "redis.*started"; then
    brew services start redis 2>/dev/null || true
fi
sleep 2

# ── Database ────────────────────────────────────────────────────────────────
echo "Setting up database..."
if ! psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw assistant; then
    echo "  Creating database 'assistant'..."
    createdb assistant 2>/dev/null || echo "  (may already exist)"
    # Create user if the DSN assumes a non-superuser login
    # Read password from .env if available, fall back to CHANGEME
    _pw="CHANGEME"
    if [ -f "$PROJECT_DIR/.env" ]; then
        _pw=$(grep -E '^POSTGRES_PASSWORD=' "$PROJECT_DIR/.env" | head -1 | cut -d= -f2-)
        _pw="${_pw:-CHANGEME}"
    fi
    psql -d assistant -c "CREATE USER assistant WITH PASSWORD '$_pw';" 2>/dev/null || true
    psql -d assistant -c "GRANT ALL PRIVILEGES ON DATABASE assistant TO assistant;" 2>/dev/null || true
    psql -d assistant -c "GRANT ALL ON SCHEMA public TO assistant;" 2>/dev/null || true
    psql -d assistant -c "ALTER DATABASE assistant OWNER TO assistant;" 2>/dev/null || true
fi

echo "Running Alembic migrations..."
pipenv run alembic upgrade head
echo ""

# ── Directory layout ────────────────────────────────────────────────────────
echo "Ensuring volume directories exist..."
mkdir -p "$PROJECT_DIR/volumes/audit_log" "$PROJECT_DIR/volumes/logs" \
         "$PROJECT_DIR/projects" "$PROJECT_DIR/skills"
echo ""

# ── Git hooks ───────────────────────────────────────────────────────────────
echo "Installing git pre-commit hook..."
if [ -d "$PROJECT_DIR/.git" ]; then
    cat > "$PROJECT_DIR/.git/hooks/pre-commit" << 'HOOK'
#!/usr/bin/env bash
# Enforce CHANGELOG updates when src/ changes.
set -e
changed_src=$(git diff --cached --name-only | grep -E '^src/' || true)
if [ -n "$changed_src" ]; then
    changed_changelogs=$(git diff --cached --name-only | grep -E 'CHANGELOG\.md$' || true)
    if [ -z "$changed_changelogs" ]; then
        echo "✗ src/ changed but no CHANGELOG.md updated."
        echo "  Affected files:"
        echo "$changed_src" | sed 's/^/    /'
        echo "  Update .context/modules/<module>/CHANGELOG.md for each module you touched."
        exit 1
    fi
fi
HOOK
    chmod +x "$PROJECT_DIR/.git/hooks/pre-commit"
    echo "  Installed."
else
    echo "  Skipped (no .git)."
fi
echo ""

echo "=== Bootstrap done ==="
echo ""
echo "Next steps:"
echo "  1. Edit $PROJECT_DIR/.env with your real secrets"
echo "  2. Run 'claude login' if you haven't"
echo "  3. bash scripts/run.sh start"
echo "  4. bash scripts/install-launchd.sh  (optional: auto-start on boot)"
