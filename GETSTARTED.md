# Get started: ai-server

Exact commands to stand up the new server on your Mac Mini. Run these *after*
`TEARDOWN.md`.

## Prerequisites

You need these installed. Most you already have.

```bash
# Check (these should all succeed):
brew --version
python3 --version   # 3.12+
pipenv --version
psql --version      # postgresql@15
redis-cli --version
gh --version        # github CLI
claude --version    # Claude Code CLI

# Install any missing:
brew install python@3.12 pipenv postgresql@15 redis gh
curl -fsSL https://claude.ai/install.sh | bash   # Claude Code if missing
```

Start the infra services if they're not running:
```bash
brew services start postgresql@15
brew services start redis
```

## 1. Create the GitHub repo

On github.com (or via `gh`):
```bash
gh auth login   # if you haven't
gh repo create Piserchia/ai-server --private --description "Personal assistant server"
```

## 2. Get the code onto the Mac Mini

The Phase 1 skeleton is delivered as a tarball. Extract it into the right place:

```bash
# Target path: avoids ~/Documents (macOS FDA breaks launchd there)
mkdir -p "$HOME/Library/Application Support"
cd "$HOME/Library/Application Support"

# Extract the tarball you were given (adjust path to wherever you saved it):
tar -xzf ~/Downloads/ai-server-phase1.tar.gz
# You should now have: ~/Library/Application Support/ai-server/

cd ai-server
git init
git add .
git commit -m "Phase 1 skeleton"
git branch -M main
git remote add origin git@github.com:Piserchia/ai-server.git
git push -u origin main
```

## 3. Authenticate Claude Code

Once, interactively:
```bash
claude login
```
This opens a browser and stores credentials in `~/.claude/`.

**Important:** do not set `ANTHROPIC_API_KEY` anywhere. The server explicitly
unsets it, but if it's in your shell rc it'll keep leaking in.

```bash
# Check your shell rc for any accidental setting:
grep -r "ANTHROPIC_API_KEY" ~/.zshrc ~/.bashrc ~/.profile 2>/dev/null
# If any matches, remove them.
```

## 4. Configure secrets

```bash
cd "$HOME/Library/Application Support/ai-server"
cp .env.example .env
vi .env
```

Fill in:
- `TELEGRAM_BOT_TOKEN` — from @BotFather on Telegram. Create a new bot if you
  don't already have one, or reuse the token from the old system (first
  make sure the old bot process is fully stopped — see TEARDOWN.md).
- `TELEGRAM_ALLOWED_CHAT_IDS` — DM @userinfobot to get your numeric chat ID.
- `POSTGRES_DSN` — default is `postgresql+asyncpg://assistant:CHANGEME@localhost:5432/assistant`.
  Change the password.
- `POSTGRES_PASSWORD` — must match the password in POSTGRES_DSN.
- `WEB_AUTH_TOKEN` — random: `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`

Leave blank for now (set in later phases):
- `SERVER_DOMAIN` (Phase 3)

## 5. Bootstrap

```bash
cd "$HOME/Library/Application Support/ai-server"
bash scripts/bootstrap.sh
```

This will:
- Check all required tools are installed
- `pipenv install --dev`
- Create the `assistant` Postgres database and user
- Run Alembic migrations to create the 3 tables
- Install a git pre-commit hook that enforces CHANGELOG updates
- Create empty volume directories

If anything fails, read the error. Most common: Postgres not running, or the
user/password mismatch between your DSN and what you let bootstrap create.

## 6. Smoke test

Start the three processes in the foreground (not backgrounded, so you see output):

```bash
# Terminal 1: the runner
cd "$HOME/Library/Application Support/ai-server"
pipenv run python3 -m src.runner.main
# Should print: "runner starting" + "root=... concurrency=2 model_default=claude-sonnet-4-6"
# Leave it running.

# Terminal 2: the web gateway
cd "$HOME/Library/Application Support/ai-server"
pipenv run uvicorn src.gateway.web:app --host 127.0.0.1 --port 8080
# Visit http://localhost:8080 — you should see the dashboard shell.

# Terminal 3: the bot
cd "$HOME/Library/Application Support/ai-server"
pipenv run python3 -m src.gateway.telegram_bot
# Should print: "telegram bot starting"
# DM the bot /help — it should respond.
```

From your phone, try:
```
/help
/chat hello there
```

The `/chat` should come back within ~10s with a Sonnet response.

## 7. Switch to backgrounded

Kill the three foreground processes (Ctrl-C), then:

```bash
bash scripts/run.sh start
bash scripts/run.sh status
# Check logs:
tail -f volumes/logs/runner.log
```

## 8. Auto-start on boot (optional but recommended)

```bash
bash scripts/install-launchd.sh
```

Services will now start on login and auto-restart if they crash.

To uninstall later:
```bash
bash scripts/install-launchd.sh uninstall
```

## 9. You're on Phase 1

What works now:
- `/chat <anything>` — one-shot conversation
- `/task <anything>` — runs a generic Claude session in the server directory with
  all tools available. Router falls through to "generic" unless the description
  matches a known keyword (research, new project, fix, etc.) — in which case it
  picks a skill that doesn't exist yet (will fail gracefully).

What's next:
- **Phase 2**: the `research-report` skill. First real end-to-end workflow.
- **Phase 3**: buy the domain, set up the tunnel + Caddy, migrate bingo and market-tracker.
- **Phase 4**: `new-project`, `app-patch`, `new-skill`, `self-diagnose`, `code-review`.

Tell me when Phase 1 is up and I'll start Phase 2.

## Troubleshooting

### "ERROR: ANTHROPIC_API_KEY is set in the environment"
Something in your shell rc or launchd environment is exporting it. Find and remove:
```bash
grep -rn "ANTHROPIC_API_KEY" ~/.zshrc ~/.bashrc ~/.profile ~/.zprofile 2>/dev/null
```

### "ERROR: Claude Code CLI not found"
```bash
curl -fsSL https://claude.ai/install.sh | bash
# Close and reopen the terminal
claude --version
```

### "database 'assistant' does not exist"
```bash
createdb assistant
psql -d assistant -c "CREATE USER assistant WITH PASSWORD 'your-password';"
psql -d assistant -c "GRANT ALL PRIVILEGES ON DATABASE assistant TO assistant;"
pipenv run alembic upgrade head
```

### Bot says "Not authorized"
Your chat ID isn't in `TELEGRAM_ALLOWED_CHAT_IDS`. DM @userinfobot, copy the
numeric ID, put it in .env (comma-separated if multiple), restart the bot.

### "claude login" fails on the Mac Mini
If this is a headless Mac Mini you SSH into, `claude login` needs a browser.
Options: (a) run the command at the Mac's console with a display/keyboard,
(b) SSH with X11 forwarding, or (c) copy `~/.claude/` from a logged-in machine
that's also on your Anthropic account.
