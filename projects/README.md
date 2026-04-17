# Projects

Each subdirectory is a project, registered as its own git repo. This directory is
gitignored in the server repo — projects have independent lifecycles.

## Structure

```
projects/
├── _ports.yml                  # port allocation; never reuse ports
├── README.md                   # this file
└── <slug>/                     # e.g., bingo, market-tracker, nba-scores
    ├── .git/                   # each project is its own repo
    ├── CLAUDE.md               # project directive (inherits server CLAUDE.md)
    ├── manifest.yml            # type, port, healthcheck, start_command, etc.
    ├── .context/
    │   ├── CONTEXT.md
    │   ├── CHANGELOG.md
    │   └── skills/
    │       ├── DEBUG.md
    │       ├── PATTERNS.md
    │       └── GOTCHAS.md
    └── src/ (or build/, static/, etc. depending on type)
```

## Adding a project

Via `new-project` skill (Phase 4):

```
/task new project: NBA live scores widget, polls ESPN every 10 min
```

The skill scaffolds the directory, writes the manifest, creates a new GitHub repo,
runs `scripts/register-project.sh <slug>` to wire up Caddy + launchd, and pushes.

## Manifest schema

See `src/registry/manifest.py` for the authoritative schema.

```yaml
slug: market-tracker
name: Market Tracker
type: service              # static | service | api
subdomain: market-tracker
port: 9012
healthcheck: /health
start_command: "pipenv run python main.py"
working_dir: "."
env:
  POLYGON_API_KEY: "from_keychain:polygon_api_key"
on_update:
  cron: "*/15 * * * *"
  command: "pipenv run python scripts/refresh.py"
git:
  repo: "https://github.com/Piserchia/market-tracker"
  branch: "main"
description: "Multi-dashboard market monitoring"
```
