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
pipenv run pytest                  # ~750 tests (pure-function + local-git integration)
pipenv run python scripts/lint_docs.py   # doc/registry/contract sync checks
```

## Status

All original phases (1–6) shipped, plus the SDK-native overhaul (Phase 8,
`docs/SDK_MIGRATION_2026-07-27.md`) and the project-delivery-segregation contract
(`docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`). Current
state + open gaps: `docs/EVALUATION_2026-07-28.md`.

## License

Personal project. No license granted.
