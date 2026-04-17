# ai-server

Personal assistant server. Runs on a Mac Mini. Accepts tasks via Telegram or web,
executes them through the Claude Agent SDK, hosts resulting projects on a single
public domain.

Built to manage, diagnose, and extend itself with minimal intervention.

## What's in here

| Path | What |
|---|---|
| `src/` | Python source (~1500 LOC target) — runner, gateway, registry |
| `skills/` | Skill library. Each skill is a directory with a SKILL.md |
| `projects/` | Hosted projects. Each is its own git repo; gitignored here |
| `.context/` | Server-level context: SYSTEM.md, PROTOCOL.md, module contexts |
| `alembic/` | Database migrations (one: initial schema) |
| `scripts/` | bootstrap.sh, run.sh, install-launchd.sh, register-project.sh |
| `volumes/` | Runtime data: audit_log, logs, pids (gitignored) |
| `CLAUDE.md` | Directive that every Claude session in this repo reads first |
| `SERVER.md` | Architecture overview |

## First-time setup

On the Mac Mini:

```bash
# 1. Clone to the right place (not ~/Documents — macOS FDA blocks launchd there)
mkdir -p "$HOME/Library/Application Support"
cd "$HOME/Library/Application Support"
git clone git@github.com:Piserchia/ai-server.git
cd ai-server

# 2. Authenticate Claude Code (once)
claude login

# 3. Run the bootstrap — installs deps, creates DB, runs migrations, writes .env
bash scripts/bootstrap.sh

# 4. Edit .env with your Telegram bot token, allowed chat IDs, and a web auth token
vi .env

# 5. Start the three processes
bash scripts/run.sh start
bash scripts/run.sh status

# 6. (Optional) auto-start on boot + auto-restart on crash
bash scripts/install-launchd.sh

# 7. On your phone: message the bot
/help
```

## Daily operation

```bash
bash scripts/run.sh status                 # is it running?
tail -f volumes/logs/runner.log            # what is it doing?
tail -f volumes/audit_log/<job_id>.jsonl   # what did it do on one job?
```

Telegram:
```
/task research the NBA trade deadline
/task --model=opus --effort=high  write me a FastAPI endpoint for X
/chat how do you think about Y
/status abc12345
/rate abc12345 5
/projects
/resume                                    # clear a quota pause
```

## Design

See `SERVER.md` for architecture, `.context/SYSTEM.md` for the module graph,
and `docs/assistant-system-design.md` for the full design doc including skill
catalog, model selection framework, self-evaluation mechanics, and phase plan.

## Testing

```bash
pipenv run pytest                  # runs all tests (Phase 2: 52 pure-function tests)
pipenv run pytest tests/test_pure_functions.py -v
```

## Phases

- **Phase 1** (commit `05ad5e7`): skeleton — runner + web + bot + `chat` skill
- **Phase 2** (this commit): `research-report` skill, write-back verification hook, failure-escalation hook, 52 pure-function tests
- **Phase 3**: domain + Cloudflare tunnel + Caddy + project hosting
- **Phase 4**: expansion skills (`new-project`, `app-patch`, `new-skill`, `self-diagnose`, `code-review`)
- **Phase 5**: operations skills (`server-upkeep`, `backup`, `server-patch`, `review-and-improve`)
- **Phase 6**: polish

## License

Personal project. No license granted.
