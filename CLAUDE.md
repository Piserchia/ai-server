# CLAUDE.md — Assistant Server

You are working inside the assistant server. This directive is always in effect.

## Before you act
-1. Read `MISSION.md` for the overall mission and objectives.
0. Read `.context/INDEX.md` for a complete map of all documentation.
1. Read `SERVER.md` if you need an architecture overview.
2. For server-code work, read `.context/SYSTEM.md` and the relevant `.context/modules/<x>/CONTEXT.md`.
3. For project-scoped work: `cd projects/<slug>` and read that project's `CLAUDE.md` and `.context/CONTEXT.md` first.
4. For cross-project work (skills that touch multiple projects): read `.context/PROJECTS_REGISTRY.md` for the index of all hosted projects. Each project's `.context/CONTEXT.md` follows a standard format with Mission, Platforms, Web Serving, Architecture, and Status sections. Read the registry first, then drill into individual projects as needed.
5. For debug/patch work, tail the last 20 entries of `volumes/audit_log/<related_job_ids>.jsonl`.

## While you work

- Prefer small committed steps over big uncommitted changes.
- When you learn something non-obvious, append to the relevant skill file (`DEBUG.md`, `PATTERNS.md`, `GOTCHAS.md`).
- If you change module A's API and module B depends on A, add a warning note to B's `CONTEXT.md`.
- Never set `ANTHROPIC_API_KEY` anywhere. This server is on subscription auth.

## Before you finish

- Update `CHANGELOG.md` for every module you touched. Format: see `.context/PROTOCOL.md`.
- Update `CONTEXT.md` if the module's public interface changed.
- Update global documentation based on what you changed (see table below).
- Your final text message becomes the job's summary — make it one paragraph that describes what was done, what's left, and where to look.
- Run any tests the skill declares. If the skill doesn't declare a test command, run `pytest` in the module you touched.

## Documentation update map

When you make a change, update the corresponding global docs:

| What changed | Update these |
|---|---|
| Added/removed a skill (`skills/<name>/`) | `.context/SKILLS_REGISTRY.md` |
| Added/removed a project (`projects/<slug>/`) | `.context/PROJECTS_REGISTRY.md`, `projects/_ports.yml` (if service) |
| Added/removed a file in `src/runner/` | `.context/modules/runner/CONTEXT.md` (Paths line + public interface) |
| Added/removed a file in `src/gateway/` | `.context/modules/gateway/CONTEXT.md` |
| Added/removed a file in `src/` (any module) | `.context/SYSTEM.md` (module graph table) |
| Changed a module's public API | That module's `.context/modules/<x>/CONTEXT.md` |
| Added a new script (`scripts/`) | `.context/SYSTEM.md` (module graph) |
| Changed hosting config (Caddy, tunnel, launchd) | `.context/modules/hosting/CONTEXT.md` |
| Added a new documentation file | `.context/INDEX.md` |
| Added a new `docs/*.md` report or plan | `.context/INDEX.md`, `docs/README.md` |
| Discovered a new failure mode | `docs/Troubleshooting.md` |
| Discovered a non-obvious gotcha | Relevant `skills/GOTCHAS.md` or module skills dir |

The `scripts/lint_docs.py` script (also in the pytest suite) validates that
registries stay in sync. Run `python scripts/lint_docs.py` to check.

## Single-writer topology (dev vs production)

The repo exists in two places with strictly separated write rights:

- **Dev repo** (`~/Documents/repos/ai-server`): the ONLY birthplace of code
  and config commits. All `src/`, `scripts/`, `alembic/`, skill-frontmatter
  work happens here and reaches production via `git push` + the
  `server-deploy` skill.
- **Production checkout** (`~/Library/Application Support/ai-server`): a
  pull-only deploy target. The ONLY writes born here are runtime doc
  learnings (GOTCHAS/CHANGELOG/Troubleshooting entries written by sessions).
  Those are published automatically to the `runtime-learnings` branch by
  `scripts/sync-learnings.sh` (hourly launchd timer) — never commit on main
  in production, never hand-"rescue" doc drift again.

Deploy path: dev commit → `origin/main` → `/task deploy server` (skill
`server-deploy`: ff-only pull, migrate, pytest gate, restart). Learnings
path: prod session writes docs → sync-learnings → `origin/runtime-learnings`
→ merged into main from dev.

Enforcement (2026-07-12): production has a pre-commit guard blocking main
commits (`scripts/install-prod-hooks.sh`, re-armed on every deploy; god
break-glass bypass documented in its SKILL.md — push-in-same-session
mandatory). sync-learnings also auto-publishes any stray prod commits to
`origin/runtime-rescue-auto`. Dev-side rule: **`git fetch origin && git
merge origin/main` before starting server work and before pushing** — god
sessions and the learning sync land commits on GitHub between your pushes.

## Git push gates (every session, every push)

Run this procedure for ANY push from ANY checkout. No step is optional.

1. **Gate before commit**: the skill's verify steps are green (tests,
   healthcheck, behavior probe — red never gets committed), no secrets in
   the diff (`git diff | grep -iE 'api[_-]?key|token|secret|password'`),
   CHANGELOG updated (the pre-commit hook enforces this for `src/`).
2. **Sync before push**: `git fetch origin` and merge/rebase onto the
   target branch BEFORE pushing. Remote main moves between your pushes
   (god sessions, sync-learnings, other jobs).
3. **Rejected push**: fetch, integrate (`git pull --rebase origin <branch>`
   in projects; `git merge origin/main` in the server repo), re-run the
   gates, retry ONCE. Still failing → STOP and report the divergence with
   `git log --oneline origin/<branch>..HEAD` and the reverse. Divergence is
   a finding for a human, never an obstacle to bulldoze.
4. **Never**: force-push, rewrite pushed history, `git reset --hard`
   without first parking HEAD on a rescue branch, or push to a checkout's
   main from PRODUCTION (pre-commit guard enforces; god break-glass
   bypass requires same-session push — see `skills/god/SKILL.md`).
5. **Where pushes go**: dev server repo → `origin main` after gates.
   Workspace clones → exactly what the skill instructs (the canonical is
   ff-synced automatically after your push). Dev-repo-topology projects
   (e.g. atlas) → their dev repo only, never the runtime clone.

## Hard rules

- **Never modify `.context/PROTOCOL.md`** without an explicit human request.
- **Never add a server PR merge without `code-review` sub-agent LGTM**. Server code is always manual-merge.
- **Never modify `TELEGRAM_ALLOWED_CHAT_IDS`** — that's auth config, not data.
- **Never delete a project or skill**. Propose a PR with rationale; a human confirms.

## Key directories

- `src/` — server code
- `skills/` — skill library (markdown + support files)
- `projects/` — hosted projects (each is its own git repo, gitignored here)
- `.context/` — server-level context docs
- `volumes/audit_log/` — append-only JSONL per job
- `volumes/logs/` — process logs
