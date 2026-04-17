---
name: code-review
description: Review a code diff for correctness, security, style, and completeness
model: claude-opus-4-7
effort: high
permission_mode: plan
required_tools: [Read, Glob, Grep]
max_turns: 5
tags: [meta, quality]
---

# Code Review

You are reviewing code changes. This skill is invoked in two ways:
1. **Automatically** by the runner after code-touching sessions (via `post_review` hook)
2. **Manually** via `/task review the diff at <path>` or `/task code review <project>`

## When invoked manually

Find the diff yourself:
- If the user specifies a project: `cd projects/<slug>` and run `git diff HEAD~1`
- If the user specifies a file or path: read the file and compare with the last commit
- If unclear: run `git diff` and `git diff --cached` in the current working directory

## Evaluation criteria

Review for:
1. **Correctness**: Logic errors, off-by-ones, missing edge cases, broken invariants
2. **Security**: Hardcoded secrets, injection vulnerabilities, unsafe file operations
3. **Style**: Consistency with existing codebase patterns (not pedantic; only flag real issues)
4. **Completeness**: Missing error handling, untested paths, incomplete migrations

## Output format

Your response MUST start with exactly one of these words on the first line:
- `LGTM` — changes look good, no blocking issues
- `CHANGES` — minor issues that should be fixed but aren't blocking
- `BLOCKER` — serious issues (security, data loss, broken functionality) that must be fixed

After the verdict, explain your reasoning. Be specific — reference file names and line
numbers. Keep it concise; the summary should fit in a Telegram message.

## What NOT to flag

- Style-only nitpicks (indentation, naming conventions) unless egregiously inconsistent
- Missing type annotations on unchanged code
- Missing docstrings on unchanged code
- "Could be refactored" suggestions that don't fix a real problem
