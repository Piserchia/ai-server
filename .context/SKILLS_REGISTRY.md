# Skills registry

> Master index of all skills. Auto-generated target; for now maintained by hand.
> When you add a skill via `new-skill`, it appends to this file.

## Installed

| Skill | Model / Effort | Purpose | Phase |
|---|---|---|---|
| `chat` | Sonnet 4.6 / low | One-shot conversation, no tools | 1 |
| `research-report` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Web research + dated markdown report under `projects/research/` | 2 |
| `_writeback` | Sonnet 4.6 / low | **Internal.** Follow-up session that updates CHANGELOGs when the primary session skipped the write-back. Not user-triggerable. | 2 |
| `code-review` | Opus 4.7 / high (plan mode) | Review code diffs for correctness, security, style. Used as post-session sub-agent and standalone. | 4 |
| `app-patch` | Opus 4.7 / high | Patch existing projects — direct commit + push to main | 4 |
| `new-skill` | Opus 4.7 / high | Meta-skill: author new skills from natural-language descriptions | 4 |
| `project-evaluate` | Opus 4.7 / high | Read a project codebase and produce manifest.yml + standard .context/CONTEXT.md | 4 |
| `new-project` | Opus 4.7 / high (two-phase: plan arch then implement) | Scaffold, document, deploy, and register a new project | 4 |

| `self-diagnose` | Opus 4.7 / high | Investigate failures + apply fixes based on risk classification | 4 |
| `server-upkeep` | Sonnet 4.6 / low (→ Sonnet 4.6 / medium on failure) | Daily health audit: rotate logs, VACUUM DB, check project status, DM anomalies only | 5 |
| `server-patch` | Opus 4.7 / xhigh (post-review always, manual merge) | Modify server code (src/, scripts/, alembic/). Always PR-gated, never auto-merged | 5 |
| `review-and-improve` | Opus 4.7 / max (plan mode) | Analyze recent job data, propose tuning changes. Dispatches server-patch follow-up | 5 |
| `research-deep` | Opus 4.7 / high (-> Opus 4.7 / xhigh on failure) | Deep-dive research: 10-20 sources, 2000-5000 words, conflicting-evidence treatment | 6 |
| `idea-generation` | Sonnet 4.6 / medium | Generate 3-5 novel ideas, deduped against prior ideas in history.jsonl | 6 |
| `project-update-poll` | Haiku 4.5 / low | Run a project's configured `on_update` command. Cheap, fast, fail-silent | 6 |
| `restore` | Sonnet 4.6 / medium | Restore from backup tarball. DESTRUCTIVE -- requires explicit user confirmation | 6 |
| `_learning_apply` | Sonnet 4.6 / low | **Internal.** Appends learning proposals from the learning extractor hook to `.context/modules/<x>/skills/<CATEGORY>.md`. Not user-triggerable. | Rec 1 |
| `god` | Opus 4.7 / max (bypassPermissions, 200 turns) | Full-context, full-permission admin session. Equivalent to a human at the terminal. | — |

## Deferred

| Skill | Reason |
|---|---|
| `notify` (no-LLM MCP tool) | Originally planned for Phase 4. MCP dispatch via `enqueue_job` covers the primary use case (spawning child jobs). A dedicated no-LLM notify tool can be added if Telegram DM-on-demand is needed outside job completion. |

## Scripts (non-skill, no LLM)

| Script | Path | Phase |
|--------|------|-------|
| `backup` | `scripts/backup.sh` (launchd timer at 04:00) | 5 |
| `healthcheck-all` | `scripts/healthcheck-all.sh` (launchd timer every 5 min) | 3 |

## Conventions

- Skill directories with a leading underscore (`_writeback`) are **internal** —
  spawned by the runner, not user-triggerable via `/task`.
- Skill directory name follows the job `kind` with two rules:
  - Leading underscore preserved: `_writeback` → `skills/_writeback/`
  - Other underscores → dashes: `research_report` → `skills/research-report/`
- Each skill's YAML frontmatter is the machine contract; the markdown body
  becomes the system prompt.
- Supported frontmatter fields: `name`, `description`, `model`, `effort`,
  `permission_mode`, `required_tools`, `max_turns`, `escalation`, `post_review`,
  `tags`, `context_files`, `no_llm`. See `src/registry/skills.py:SkillConfig`.
- `context_files`: list of documentation files the session should read first.
  Injected into the server directive by `session.py:_build_server_directive()`.
