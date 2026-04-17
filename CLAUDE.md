# CLAUDE.md — Assistant Server

You are working inside the assistant server. This directive is always in effect.

## Before you act

1. Read `SERVER.md` if you need an architecture overview.
2. For server-code work, read `.context/SYSTEM.md` and the relevant `.context/modules/<x>/CONTEXT.md`.
3. For project-scoped work: `cd projects/<slug>` and read that project's `CLAUDE.md` and `.context/CONTEXT.md` first.
4. For debug/patch work, tail the last 20 entries of `volumes/audit_log/<related_job_ids>.jsonl`.

## While you work

- Prefer small committed steps over big uncommitted changes.
- When you learn something non-obvious, append to the relevant skill file (`DEBUG.md`, `PATTERNS.md`, `GOTCHAS.md`).
- If you change module A's API and module B depends on A, add a warning note to B's `CONTEXT.md`.
- Never set `ANTHROPIC_API_KEY` anywhere. This server is on subscription auth.

## Before you finish

- Update `CHANGELOG.md` for every module you touched. Format: see `.context/PROTOCOL.md`.
- Update `CONTEXT.md` if the module's public interface changed.
- Your final text message becomes the job's summary — make it one paragraph that describes what was done, what's left, and where to look.
- Run any tests the skill declares. If the skill doesn't declare a test command, run `pytest` in the module you touched.

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
