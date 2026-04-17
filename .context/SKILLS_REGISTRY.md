# Skills registry

> Master index of all skills. Auto-generated target; for now maintained by hand.
> When you add a skill via `new-skill`, it appends to this file.

## Installed

| Skill | Model / Effort | Purpose | Phase |
|---|---|---|---|
| `chat` | Sonnet 4.6 / low | One-shot conversation, no tools | 1 |
| `research-report` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Web research + dated markdown report under `projects/research/` | 2 |
| `_writeback` | Sonnet 4.6 / low | **Internal.** Follow-up session that updates CHANGELOGs when the primary session skipped the write-back. Not user-triggerable. | 2 |

## Planned (in order of build)

| Skill | Model / Effort | Phase |
|---|---|---|
| `new-project` | Sonnet 4.6 / medium (escalate Opus on complex) | 4 |
| `app-patch` | Opus 4.7 / high | 4 |
| `code-review` | Opus 4.7 / high (plan mode) | 4 |
| `new-skill` | Opus 4.7 / high | 4 |
| `self-diagnose` | Opus 4.7 / high | 4 |
| `notify` (no-LLM MCP tool) | — | 4 |
| `server-upkeep` | Sonnet 4.6 / low | 5 |
| `healthcheck-all` (script) | — | 5 |
| `backup` (script) | — | 5 |
| `server-patch` | Opus 4.7 / xhigh (plan + manual merge) | 5 |
| `review-and-improve` | Opus 4.7 / max (plan mode) | 5 |
| `research-deep` | Opus 4.7 / high | 6 |
| `idea-generation` | Sonnet 4.6 / medium | 6 |
| `project-update-poll` | Haiku 4.5 / low | 6 |
| `restore` | Sonnet 4.6 / medium | 6 |

## Conventions

- Skill directories with a leading underscore (`_writeback`) are **internal** —
  spawned by the runner, not user-triggerable via `/task`.
- Skill directory name follows the job `kind` with two rules:
  - Leading underscore preserved: `_writeback` → `skills/_writeback/`
  - Other underscores → dashes: `research_report` → `skills/research-report/`
- Each skill's YAML frontmatter is the machine contract; the markdown body
  becomes the system prompt.
