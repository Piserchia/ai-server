# Skills registry

> Master index of all skills. Auto-generated target; for now maintained by hand.
> When you add a skill via `new-skill`, it appends to this file.

## Installed

| Skill | Model / Effort | Purpose | Phase |
|---|---|---|---|
| `chat` | Sonnet 4.6 / low | One-shot conversation, no tools | 1 |
| `research-report` | Sonnet 4.6 / medium (→ Opus 4.7 / high on failure) | Web research + dated markdown report under `projects/research/` | 2 |
| `_writeback` | Sonnet 4.6 / low | **Internal.** Follow-up session that updates CHANGELOGs when the primary session skipped the write-back. Not user-triggerable. | 2 |
| `code-review` | Opus 4.7 / high (plan mode) | 4 |
| `app-patch` | Opus 4.7 / high | Patch existing projects — direct commit + push to main | 4 |
| `new-skill` | Opus 4.7 / high | Meta-skill: author new skills from natural-language descriptions | 4 |
| `project-evaluate` | Opus 4.7 / high | Read a project codebase and produce manifest.yml + standard .context/CONTEXT.md | 4 |
| `new-project` | Opus 4.7 / high (two-phase: plan arch then implement) | Scaffold, document, deploy, and register a new project | 4 |

| `self-diagnose` | Opus 4.7 / high | Investigate failures + apply fixes based on risk classification | 4 |

## Planned (in order of build)

| Skill | Model / Effort | Phase |
|---|---|---|
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
