# Mission

> Anchoring document. If anything in the design stops serving an objective
> below, the design is wrong — not the objective.

## Mission statement

Build a personal assistant server that **runs continuously on a Mac Mini**,
accepts natural-language requests via Telegram or web, executes them through
the Claude Agent SDK, and **hosts the resulting projects on a single public
domain** — while managing, diagnosing, and extending itself and its project
catalog with minimal human intervention.

The system is single-tenant (Chris only). It prefers **documenting itself
well** over trying to be clever. It prefers **Claude subscription** over API
billing. It prefers **PR gates** over autonomous code writes.

## Objectives and how we accomplish them

Each objective maps to concrete design elements in this repo. If an objective
isn't served by anything in the table, we've drifted.

### A. Continuous personal-assistant behavior

| Element | How it serves the objective |
|---|---|
| 3 long-running processes (runner / web / bot) | Always-on availability |
| launchd KeepAlive on all 3 + Caddy + cloudflared | Auto-restart on crash |
| `~/Library/Application Support/ai-server/` install path | Avoids macOS FDA rule that broke the old launchd setup |
| Subscription-auth check on startup | Fails loud and early rather than burning API tokens by accident |

### B. Scheduled research, polling, upkeep

| Element | How it serves the objective |
|---|---|
| `schedules` table + `_scheduler_loop` in runner | Cron-based job enqueuing |
| `research-report` skill (Phase 2) | Weekly/daily research dropped into `projects/research/` |
| `project-update-poll` skill (Phase 6) | Per-project data refresh on their own cron |
| `server-upkeep` skill (Phase 5) | Daily 3am log rotation, disk check, cert check, anomaly report |

### C. App creation + deployment

| Element | How it serves the objective |
|---|---|
| `new-project` skill (Phase 4) | Scaffold a project from a description |
| `manifest.yml` schema + `src/registry/manifest.py` | Declarative contract for each project (type, port, healthcheck, etc.) |
| `scripts/register-project.sh` (Phase 3) | Wires a new project into Caddy + launchd |
| Separate-repo-per-project convention (`.gitignore` excludes `projects/*/`) | Each project has its own git history, independent lifecycle |
| `gh` CLI dependency | `new-project` auto-creates GitHub repos |

### D. Multi-project hosting on a single public domain

| Element | How it serves the objective |
|---|---|
| Cloudflare named tunnel (Phase 3) | Stable `*.yourdomain.com` → Mac Mini, survives restarts |
| Caddy reverse proxy with per-project snippets | `bingo.yourdomain.com`, `market-tracker.yourdomain.com`, etc. |
| `projects/_ports.yml` registry | Port collisions prevented; increment-only |
| `projects` Postgres table | Runtime view of what's hosted |
| `/api/projects` + dashboard tiles | Human-visible "what's live right now" |

### E. Idea generation

| Element | How it serves the objective |
|---|---|
| `idea-generation` skill (Phase 6) | Structured ideas + dedup against a history log |
| `schedules` table | "Generate 3 ideas every Monday morning" is a single row |

### F. Self-management

| Element | How it serves the objective |
|---|---|
| `healthcheck-all` script (Phase 5) | Per-project HTTP probes every 5 min |
| `projects.last_healthy_at` column | Dashboard shows stale projects |
| `backup` skill (Phase 5) | Nightly pg_dump + projects tarball |
| `server-upkeep` skill (Phase 5) | Log rotation, DB VACUUM, cert expiry check |
| `src/runner/quota.py` | Detects subscription quota hit → pauses queue → auto-resumes |
| Telegram quota notifier | User is informed, not surprised, on pause and resume |

### G. Self-debugging and self-fixing

| Element | How it serves the objective |
|---|---|
| `self-diagnose` skill (Phase 4) | Opus 4.7 / high reads audit logs + service logs, proposes or applies low-risk fixes |
| Event trigger: 2 failures in same skill / 10 min | Auto-enqueues `self-diagnose` without user action |
| `app-patch` / `server-patch` skills | Self-diagnose delegates the fix through the normal patching pathway |
| Append-only audit logs at `volumes/audit_log/<job_id>.jsonl` | "What was Claude doing when it broke?" is grep-able |

### H. Self-improvement

| Element | How it serves the objective |
|---|---|
| `jobs.resolved_skill` / `resolved_model` / `resolved_effort` columns | Collected from day 1 — substrate for tuning |
| `jobs.user_rating` (1-5) + `/rate` command in Telegram + web | Quality signal per job |
| `jobs.review_outcome` (LGTM / changes_requested / blocker) | Quality signal from `code-review` sub-agent |
| `review-and-improve` skill (Phase 5, monthly, Opus 4.7 / max in plan mode) | Analyzes patterns, proposes changes as PRs |
| **PRs only, no silent edits** (INV-4, INV-13) | You see every change; skills auto-merge on `code-review` LGTM; server code always manual-merge |

### I. Self-expansion

| Element | How it serves the objective |
|---|---|
| `new-project` skill | Adds a project |
| `new-skill` skill | Adds a new skill (meta — the system learns new capabilities) |
| `server-patch` skill (Phase 5) | Modifies server code, always PR-gated, always needs `code-review` LGTM |
| SKILL.md as data, not code | Adding capability doesn't require a code deploy |

### J. Smart model selection

| Element | How it serves the objective |
|---|---|
| SKILL.md YAML frontmatter (`model`, `effort`, `permission_mode`) | Each skill declares its own optimal config |
| `src/runner/router.py` rules (coding intent → `app-patch` → Opus 4.7 / high) | Coding reaches the right tier without thinking |
| `--model=` / `--effort=` flags in `/task` | User override |
| Per-job `payload` precedence over skill frontmatter | Flags win when specified |
| Escalation frontmatter (`on_failure`, `on_quality_gate_miss`) | Cheap models first; auto-promote on failure (catches the "simple task that turned out complex") |
| Global default Sonnet 4.6 | Speed + subscription efficiency for the 80% case |
| Auto-tuning monthly retrospective (Phase 5) | Recommends default changes based on actual success rates |

### K. Subscription economics

| Element | How it serves the objective |
|---|---|
| Bundled Claude Code CLI auth (no API key) | Uses your Max 5x subscription |
| Runner startup check aborts if `ANTHROPIC_API_KEY` is set | Prevents accidental API billing |
| `bootstrap.sh`, `run.sh`, `install-launchd.sh` all `unset ANTHROPIC_API_KEY` | Defense in depth |
| `MAX_CONCURRENT_JOBS=2` default | Leaves subscription headroom for your direct Claude use |
| `src/runner/quota.py` detection + auto-pause | Quota exhaustion is a known state, not a failure |

### L. Documentation that compounds

This is the piece that makes the system work across weeks and months. Every
element feeds or reads from it.

| Element | How it serves the objective |
|---|---|
| Server-level `CLAUDE.md` | Every Claude session in the repo auto-loads this |
| `SERVER.md` | Architecture overview for a returning Claude or human |
| `.context/SYSTEM.md` | Module graph, conventions, invariants — source of truth |
| `.context/PROTOCOL.md` (copied verbatim from old repo — it was the only good thing) | Write-back rules enforced per session |
| `.context/modules/<x>/CONTEXT.md` + `CHANGELOG.md` + `skills/` | Per-module state + history + learned patterns |
| Per-project `.context/` (Phase 3+) | Projects get the same treatment |
| `volumes/audit_log/<job_id>.jsonl` | Permanent record of every tool use, every text block, every error |
| `<job_id>.summary.md` | One-paragraph human-readable per job |
| Write-back verification hook (Phase 2) | Runner spawns a follow-up if a session modified code but didn't update CHANGELOG |
| Git pre-commit hook | Blocks commits touching `src/` without CHANGELOG update |

### M. Safety ceilings

Things the system is **explicitly prohibited from doing** autonomously:

- Server code changes never auto-merge (INV-4)
- Project deletion requires Telegram Y/N confirmation
- Skill deletion requires Telegram Y/N confirmation
- `TELEGRAM_ALLOWED_CHAT_IDS` is config-only, not data — system can't modify it
- `.context/PROTOCOL.md` is read-only to sessions (propose changes via PR like anything else)
- Cannot deploy to cloud environments (no AWS, no Heroku, etc.)
- Cannot send emails from your account
- Cannot publish to your public social accounts

## Non-goals (explicit scope ceilings)

- Not a general-purpose agent framework
- Not multi-user
- Not a replacement for Claude Code on your laptop
- Not a continuous silent self-improver — batched, proposed, reviewed
- Not cross-provider — Anthropic only
- Not fine-tuning — use what Anthropic ships

## Phase map (shipped vs planned)

| Phase | Status | Plan doc | What it proves |
|---|---|---|---|
| 1 — Skeleton | **SHIPPED** (commit `05ad5e7`) | — (in-repo) | Jobs flow; SDK integration; audit log; subscription auth; 3-process topology |
| 2 — First real skill + write-back + escalation + tests | **SHIPPED** (commit `6e58fe3`) | — (in-repo) | `research-report` runs end-to-end; write-back hook enforces CHANGELOG updates; failure escalation promotes Sonnet → Opus 4.7 automatically; 52-test pure-function suite |
| 3 — Domain + tunnel + Caddy + bingo + market-tracker | **SHIPPED** (commit `9f47681`) | [`docs/PHASE_3_PLAN.md`](docs/PHASE_3_PLAN.md) | Multi-project hosting works; `bingo.chrispiserchia.com` + `market-tracker.chrispiserchia.com` live |
| 4 — Expansion skills + MCP servers + event triggers | **SHIPPED** | [`docs/PHASE_4_PLAN.md`](docs/PHASE_4_PLAN.md) | 7 skills (code-review, new-project, app-patch, new-skill, self-diagnose, project-evaluate) + 2 MCP servers + event-triggered auto-diagnose; 102-test suite |
| 5 — Operations (upkeep, backup, server-patch, review-and-improve) | **SHIPPED** | [`docs/PHASE_5_PLAN.md`](docs/PHASE_5_PLAN.md) | Nightly backup, daily upkeep, PR-gated server patches, idle-queue retrospectives; 109-test suite |
| 6 — Polish (`research-deep`, `idea-generation`, `project-update-poll`, `restore`) | planned | [`docs/PHASE_6_PLAN.md`](docs/PHASE_6_PLAN.md) | Full catalog |

**For debugging Phase 1/2 issues in Claude Code CLI:** [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

Each phase plan is self-contained — a future Claude session with only the repo
and the plan doc can execute that phase without additional context.

## How we know we're on track

Each phase ends with a concrete, verifiable outcome. Not "it works" — specific
observable things:

- **Phase 1 done**: `/chat hello` returns a Sonnet reply in <15s. `/task <anything>`
  creates a Job row and writes an audit log file. Dashboard shows the job.
- **Phase 2 done**: scheduled `research-report` drops a real markdown file
  in `projects/research/` on schedule, committed to git, TL;DR DM'd.
- **Phase 3 done**: `bingo.yourdomain.com` loads from the public internet,
  served from the Mac Mini.
- **Phase 4 done**: `/task new project: <description>` results in a live,
  public, documented project in under 10 minutes with no further input.
- **Phase 5 done**: you don't have to think about the server for a week.
  The monthly retrospective shows up as a PR.

---

*When in doubt, re-read this document. If the design seems to be wandering,
point at a row here and ask "which objective does this serve?"*
