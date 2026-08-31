# ai-server

Personal assistant server. Runs on a Mac Mini. Accepts tasks via Telegram or web,
executes them through the Claude Agent SDK, hosts resulting projects on a single
public domain.

Built to manage, diagnose, and extend itself with minimal intervention.

## What's in here

| Path | What |
|---|---|
| `src/` | Python source — runner, gateway, registry |
| `skills/` | Skill library. Each skill is a directory with a SKILL.md (data, not code) |
| `projects/` | Hosted projects. Each is its own git repo; gitignored here |
| `.context/` | Server-level context: SYSTEM.md, PROTOCOL.md, module contexts |
| `alembic/` | Database migrations |
| `scripts/` | bootstrap.sh, run.sh, install-launchd.sh, register-project.sh |
| `volumes/` | Runtime data: audit_log, logs (gitignored) |
| `CLAUDE.md` | Directive that every Claude session in this repo reads first |
| `SERVER.md` | Architecture overview |
| `MISSION.md` | Mission + objectives (the anchoring doc) |
| `docs/` | Evaluations, plans, troubleshooting (see `docs/README.md`) |

## First-time setup

This system runs from **two checkouts** (CLAUDE.md § single-writer topology):
production lives in `~/Library/Application Support/ai-server` (launchd's
working directory; pull-only), and all code is born in a second dev clone at
`~/Documents/repos/ai-server`. A rebuild needs BOTH.

On the Mac Mini:

```bash
# 1a. Clone PROD to the right place (not ~/Documents — macOS FDA blocks launchd there)
mkdir -p "$HOME/Library/Application Support"
cd "$HOME/Library/Application Support"
git clone git@github.com:Piserchia/ai-server.git
cd ai-server

# 1b. Clone the DEV writer (where commits are born)
mkdir -p ~/Documents/repos
git -C ~/Documents/repos clone git@github.com:Piserchia/ai-server.git

# 2. Authenticate Claude Code (once)
claude login

# 3. Run the bootstrap — installs deps (from the committed Pipfile.lock),
#    creates DB, runs migrations, writes .env
bash scripts/bootstrap.sh

# 4. Edit .env with your Telegram bot token, allowed chat IDs, and a web auth token
vi .env

# 5. Install launchd supervision — launchd OWNS the processes in production
bash scripts/install-launchd.sh
bash scripts/run.sh status        # reports launchd state when units exist

# 6. Public domain: cloudflared runs as a SYSTEM LaunchDaemon that
#    install-launchd.sh does NOT install — re-install it by hand
#    (`cloudflared tunnel login` + `sudo cloudflared service install`;
#    see .context/modules/hosting/CONTEXT.md). Postgres/redis via brew services.

# 7. On your phone: message the bot
/help
```

## Daily operation

```bash
bash scripts/run.sh status                 # launchd-aware status (refuses `start` when launchd owns the services)
curl -s localhost:8080/health | jq         # runner heartbeat + real PG queue backlog
tail -f volumes/logs/runner.out.log        # what is it doing?
tail -f volumes/audit_log/<job_id>.jsonl   # what did it do on one job?
launchctl kickstart -k gui/$UID/com.assistant.runner   # restart a service
```

Telegram (bare natural language works too — it's NL-first; commands are the explicit path):
```
/task research the NBA trade deadline
/task --model=opus --effort=high  write me a FastAPI endpoint for X
/chat how do you think about Y
/status abc12345          # job status
/tasks                    # your open task threads
/projects                 # what's hosted
/schedule …               # manage recurrences
/resume                   # clear a quota pause
/help                     # full command list
```

## Design

See `MISSION.md` for objectives, `SERVER.md` for architecture, `.context/SYSTEM.md`
for the module graph + invariants, and `.context/INDEX.md` for the full doc map.
Execution is **Claude Agent SDK, in-process, subscription auth** (no API key, no
containers — see `docs/SDK_MIGRATION_2026-07-27.md`).

## Testing

```bash
pipenv run pytest                  # full suite (pure-function + local-git integration; count grows — don't pin it here)
pipenv run python scripts/lint_docs.py   # doc/registry/contract sync checks
```

## Status

All original phases (1–6) shipped, plus the SDK-native overhaul (Phase 8,
`docs/SDK_MIGRATION_2026-07-27.md`) and the project-delivery-segregation contract
(`docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`). Current
state + open gaps: `docs/EVALUATION_2026-07-28.md`.

## License

Personal project. No license granted.
