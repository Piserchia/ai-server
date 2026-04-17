# Skills

Each subdirectory is a skill. A skill is a directory containing a `SKILL.md` and
any supporting files (templates, examples, prompts).

## SKILL.md structure

```markdown
---
name: <slug>
description: <one sentence>
model: claude-sonnet-4-6 | claude-opus-4-7 | claude-haiku-4-5-20251001
effort: low | medium | high | xhigh | max
permission_mode: default | acceptEdits | bypassPermissions | plan
required_tools: [Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch, AskUserQuestion]
max_turns: <int, optional>
escalation:
  on_failure: { model: ..., effort: ... }
  on_quality_gate_miss: { model: ..., effort: ... }
post_review:
  trigger: always | on_server_code_changes | on_project_apps | never
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
tags: [...]
no_llm: false    # set true for script-only skills (backup, healthcheck-all)
---

# Human-readable title

## When to use
...

## Procedure
...

## Quality gate
...

## Gotchas (living section)
...
```

The YAML frontmatter is the machine-readable contract; the body becomes the system
prompt for the session.

## Currently installed

See `.context/SKILLS_REGISTRY.md`.

## Adding a skill

Don't hand-edit — use the `new-skill` skill:

```
/task new skill: every morning summarize overnight BTC price action
```

The `new-skill` skill drafts the SKILL.md, runs a `code-review` sub-agent, and
opens a PR (auto-merges on LGTM per the configured policy).
