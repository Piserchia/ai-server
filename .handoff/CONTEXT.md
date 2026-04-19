# Context for CLI session

## What this repo is

`ai-server` is Chris's personal/work AI server. It runs an agentic system that
accepts jobs via Telegram, dispatches them through a runner that selects
skills, executes them via `claude-agent-sdk`, and maintains a persistent
learning/retrospective loop via review sessions.

Key moving parts:

- **Gateway** (`src/gateway/`) — Telegram bot + web API frontends
- **Runner** (`src/runner/`) — job scheduler, session builder, retrospective
  rollups, learning extractor (Rec 1), proposals (Rec 10)
- **Registry** (`src/registry/`) — skill + project manifest loaders
- **DB** (`src/models.py`, `src/db.py`, `alembic/`) — Postgres + Redis
- **Skills** (`skills/`) — directory of SKILL.md files (one per agent skill)
- **Context system** (`.context/`) — three-layer architecture per
  `.context/PROTOCOL.md`: `SYSTEM.md` (root), per-module `CONTEXT.md`,
  skill files (`GOTCHAS.md`, `PATTERNS.md`, `DEBUG.md`)

## Conventions this session must follow

### Writing code

- Python 3.11+, type hints everywhere
- `SQLAlchemy 2.0` style (Mapped / mapped_column), async engine
- Pure functions are unit-tested; async DB ops are integration-tested only
  (no sandbox Postgres)
- Prefer composition over inheritance; small files over monoliths

### Docs + context

- Every session that modifies a module's code must **append a CHANGELOG
  entry** to that module's `.context/modules/<module>/CHANGELOG.md`.
  Newest entries at top. See `.context/PROTOCOL.md` for the enforced format.
- When adding new source files, update `.context/SYSTEM.md` module graph
  AND the relevant `.context/modules/<module>/CONTEXT.md` paths line.
- New skills go in `skills/<name>/SKILL.md` with frontmatter. Internal
  skills (not user-callable) start with `_`.

### Migrations

- Never edit existing alembic migrations. Always add a new one.
- Current: `001_initial.py`, `002_proposals_table.py`.
- Partial indexes: use `op.execute("CREATE INDEX ...")` with raw SQL.

### Commits

- Commit format (enforced by user): `feat(rec-N): <one line>` for
  recommendation work, `docs: <one line>` for doc-only updates, `fix: ...`
  for bugs. Body references `docs/EVALUATION_2026-04-18.md § 7 Recommendation N`.
- **Every feature commit is followed by a status-table update commit**:
  the commit SHA must be recorded in `docs/EVALUATION_2026-04-18.md`'s
  status table. This is non-negotiable per user instruction.

### Testing

```bash
python3 scripts/lint_docs.py
# expected: 5/5 PASS

SERVER_ROOT=$(pwd) POSTGRES_DSN="postgresql+asyncpg://x:y@localhost/x" PYTHONPATH=. \
  python3 -m pytest tests/ -v
```

If deps aren't installed:
```bash
pip install --break-system-packages --ignore-installed \
  pytest pyyaml pydantic pydantic-settings structlog claude-agent-sdk
```

## Key files to know

| Path | What it is |
|------|-----------|
| `docs/EVALUATION_2026-04-18.md` | THE evaluation doc. 15 recommendations in § 7, status table at top. |
| `.context/SYSTEM.md` | Root of context system; module graph |
| `.context/PROTOCOL.md` | Rules for how sessions read/write the context system |
| `src/models.py` | ORM. After Rec 10: Job, Schedule, Project, Proposal |
| `src/db.py` | async_session + Redis channel constants |
| `src/runner/main.py` | Job processor main loop; `_process_job` has the hook chain |
| `src/runner/session.py` | `_build_server_directive`; context_files resolution at runtime |
| `src/runner/retrospective.py` | Skill performance rollups (Rec 2 adds to this) |
| `src/runner/learning.py` | Learning extractor (Rec 1) |
| `src/runner/proposals.py` | Proposal tracking helpers (Rec 10) |
| `src/gateway/telegram_bot.py` | User commands via Telegram |
| `src/gateway/web.py` | HTTP API + dashboard |
| `src/gateway/jobs.py` | `enqueue_job()` |
| `src/audit_log.py` | JSONL per-job audit trail — `volumes/audit_log/<job_id>.jsonl` |
| `scripts/lint_docs.py` | 5 lint checks that run on every commit |

## Architecture facts worth knowing

- **No pgvector, no DuckDB, no foreign tables** — Phase 1 explicitly keeps
  persistence simple.
- **Audit trail is JSONL files, not a DB table.** See `src/audit_log.py`.
  Events: `job_started`, `text`, `tool_use`, `tool_result`, `thinking`,
  `job_completed`, `job_failed`, `job_cancelled`, `job_requeued_for_quota`,
  `note`.
- **`context_files` in skill frontmatter are static paths** resolved at
  session-build time (`src/runner/session.py:_build_server_directive` lines
  103-106). No `<slug>` templating; slug-specific paths stay in skill body prose.
- **Kinds starting with `_`** are internal (non-user-callable). Skill name
  resolution preserves the leading `_`. Example: `_learning_apply` from Rec 1.
- **Runner hooks in `_process_job`** (after `_finish_job(completed)`):
  `_maybe_review` → `_verify_writeback` → `maybe_extract_and_enqueue` (Rec 1
  learning extractor). All wrapped in `try/except` with `log.exception`; hooks
  are non-fatal.

## Things that have bitten prior sessions (gotchas)

- **Sandbox Postgres isn't available** — async DB ops can't be unit-tested
  in the chat-session sandbox. Always separate pure helpers from async DB
  ops for testability.
- **claude_agent_sdk may not be pip-installable in a sandbox** — production
  has it in Pipfile. If pytest collection fails on a sandbox because of
  missing `claude_agent_sdk`, that's NOT a real failure. Ship anyway and
  mark the rec resolved (see Rec 11's history).
- **Partial-index Alembic syntax** — `op.create_index(postgresql_where=...)`
  works but raw `op.execute(...)` keeps the SQL readable.
- **Don't edit existing migrations.** Always add a new one.
- **The "status table SHA update" step cannot be skipped.** Every prior
  session that "forgot" it got called out.

## User preferences

- **Short, direct answers**. Chris will push back on long responses.
- **Strict workflow** — the 7-step ship recipe is the iron rule:
  implement → test → commit feat → push → update status table → commit docs → push.
- **Don't paste long code back into chat** — use files, PRs, or the CLI.

## Open thread: PAT rotation

The PAT `ghp_REDACTED` has been in plaintext
across 8+ session transcripts on claude.ai. It's been acknowledged across
sessions but never rotated. Please rotate.
