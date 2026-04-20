# Skill Template

> This is a reference template, not an installable skill. Copy the structure
> below when creating a new skill. See `skills/new-skill/SKILL.md` for the
> automated skill-creation workflow.

---

## Frontmatter (required)

```yaml
---
name: <kebab-case-name>
description: <one-line summary of what the skill does>
model: <claude-opus-4-7 | claude-sonnet-4-6 | claude-haiku-4-5-20251001>
effort: <low | medium | high | xhigh | max>
permission_mode: <default | acceptEdits | bypassPermissions | plan>
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: <integer>
# Optional fields:
post_review:
  trigger: always           # or: never (default)
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
escalation:
  on_failure:
    model: <model>
    effort: <effort>
context_files: ["path/relative/to/server/root"]
tags: [<category>, <needs-projects-mcp>, <needs-dispatch-mcp>]
---
```

## Body sections

### # <Skill Name>

One paragraph explaining what this skill does and when it runs.

### ## Inputs

What the skill receives from the job description and payload. Document:
- Required fields and where to find them
- How to parse the target from free-form descriptions
- When to use `AskUserQuestion` vs inferring

### ## Procedure

Numbered steps the skill follows. Each step should be a `### N. <action>`
subsection. Be specific about commands, file paths, and decision points.

### ## Quality gate

Self-verification checklist before marking the job done. Format as a
markdown checkbox list:

```markdown
- [ ] Check 1 passed
- [ ] Check 2 passed
- [ ] Changes committed (if applicable)
```

### ## Gotchas (living section)

Known pitfalls discovered by prior sessions. New entries should be appended
here by sessions that learn something reusable. Format:

```markdown
- **<short title>**: <one-line description of the trap and how to avoid it>
```

## Optional sections

- **## Output format** — when the skill produces structured output (reports,
  proposals, assessments), document the exact format
- **## Error handling** — what to do on specific failure modes (e.g., "if
  git push fails, pull --rebase and retry")
- **## Protocol** — reference to PROJECT_PROTOCOL.md or PROTOCOL.md if the
  skill has write-back obligations
- **## Hard limits** — non-negotiable rules (e.g., "never auto-merge",
  "never modify .env files")

## Conventions

- Internal skills (not user-triggerable) prefix their name with `_`
  (e.g., `_writeback`, `_learning_apply`)
- Skills that need project introspection add `needs-projects-mcp` to tags
- Skills that need to spawn child jobs add `needs-dispatch-mcp` to tags
- Post-review is recommended for all code-modifying skills
- Escalation is recommended for high-effort skills that might fail on
  complex inputs
