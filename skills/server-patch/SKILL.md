---
name: server-patch
description: Modify server code (src/, scripts/, alembic/). Always PR-gated, never auto-merged.
model: claude-opus-4-7
effort: xhigh
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
post_review:
  trigger: always
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
context_files: [".context/SYSTEM.md", ".context/PROTOCOL.md"]
tags: [server, maintenance, manual-merge-required, needs-projects-mcp]
---

# Server Patch

You are modifying the assistant server's own code. This is the most sensitive
skill in the system: you are patching the infrastructure that runs you. Every
change is PR-gated and requires human approval to merge. You never merge your
own PRs. You never commit to main.

## Hard rules

These are non-negotiable. Violating any of them is a blocking failure.

1. **Never commit to `main`.** Always work on a branch.
2. **Always branch from `main`** with the naming pattern `server-patch/<slug>`,
   where `<slug>` is a short kebab-case description (e.g., `server-patch/fix-quota-reset`).
3. **Always create a PR** via `gh pr create`. Never merge your own PR.
4. **Never touch `.env`** or any file containing secrets/credentials.
5. **Never modify `TELEGRAM_ALLOWED_CHAT_IDS`** — that is auth config.
6. **Never modify `.context/PROTOCOL.md`** without an explicit human request.
7. **Never set or reference `ANTHROPIC_API_KEY`** anywhere.
8. **Run tests before pushing.** If tests fail, fix them or explain why in the PR.

## Procedure

### 1. Orient

Read the relevant context before touching any code:

- Read `.context/SYSTEM.md` for invariants.
- Read `.context/modules/<module>/CONTEXT.md` for the module you are changing.
- If changing a module that other modules depend on, read those dependents'
  `CONTEXT.md` files too.
- Read the job description and any linked audit logs to understand the problem.

### 2. Branch

```bash
git checkout main
git pull --ff-only
git checkout -b server-patch/<slug>
```

Choose a descriptive `<slug>` from the job description (max 50 chars, kebab-case).

### 3. Patch

Make your changes. Follow the existing code style. Prefer small, focused diffs.

- If you change a module's public interface, update its `CONTEXT.md` with
  a warning note about the change.
- If you change module A and module B depends on A, add a note to B's
  `CONTEXT.md` flagging the upstream change.

### 4. Test

```bash
pipenv run pytest tests/ -v
```

All tests must pass. If a test fails:

- If the failure is caused by your change, fix it.
- If the failure is pre-existing and unrelated, note it in the PR body but
  do not suppress or skip it.
- Never use `pytest --no-header -rN` or `-q` to hide output. Full verbose
  output is required.

### 5. Write CHANGELOG

Prepend an entry to `.context/modules/<module>/CHANGELOG.md` for every module
you touched. Follow the existing format:

```markdown
## YYYY-MM-DD — <short title>

**Files created**: <list or "none">
**Files changed**: <list>
**Why**: <one paragraph>
**Side effects**: <any, or "None">
**Gotchas discovered**: <any, or "None">
```

### 6. Commit

Stage and commit with a descriptive message. Include metadata trailers:

```bash
git add -A
git commit -m "$(cat <<'EOF'
<type>: <short description>

<body — what changed and why>

Requires-migration: yes | no
Requires-env-change: yes | no
Rollback: <how to revert if needed>
EOF
)"
```

Commit types: `fix`, `feat`, `refactor`, `docs`, `test`, `chore`.

### 7. Push and PR

```bash
git push -u origin server-patch/<slug>
```

Create the PR with a structured body:

```bash
gh pr create --title "<type>: <short title>" --body "$(cat <<'EOF'
## Summary

<1-3 bullet points explaining what changed and why>

## Changes

<file-by-file or module-by-module breakdown>

## Test results

<paste test output or summary>

## Metadata

- Requires-migration: yes | no
- Requires-env-change: yes | no
- Rollback: <how to revert>

## Checklist

- [ ] Tests pass (`pipenv run pytest tests/ -v`)
- [ ] CHANGELOG updated for every module touched
- [ ] CONTEXT.md updated if public interface changed
- [ ] No secrets in diff
- [ ] No commits to main
EOF
)"
```

### 8. Final summary

Your final text message must include:

- The PR URL
- A one-line description of what was changed
- Whether tests passed
- Whether migration or env changes are needed
- Any risks or caveats the human reviewer should pay attention to

Example:

```
PR: https://github.com/<org>/<repo>/pull/42
Changed: Fixed quota reset logic that was skipping paused jobs.
Tests: 52 passed, 0 failed.
Migration: no. Env change: no.
Watch: The quota.py change affects the scheduler loop — verify pause/resume behavior manually.
```

### 9. Mark proposal applied (if this PR implements a proposal)

If the PR body or the dispatching job's description contains a
`Proposal-ID: <uuid>` marker (emitted by `review-and-improve` per Rec 10),
update the row in the `proposals` table once the PR is merged:

```python
from src.runner.proposals import extract_proposal_id, mark_proposal_merged

pid = extract_proposal_id(pr_body_or_dispatch_description)
if pid is not None:
    merged = await mark_proposal_merged(pid, pr_url)
    # merged=True: row transitioned from pending/rejected → merged.
    # merged=False: no matching row or already terminal — not an error.
```

Call this AFTER the PR is actually merged. If there's no `Proposal-ID:`
marker, skip this step silently — not every PR originates from a proposal.

This closes the feedback loop: `review-and-improve` won't re-propose the
same change because the dedup query will see the merged row and skip.

## Gotchas (living section — append when you learn something)

- `pipenv run pytest` must be run from the repo root, not from `src/`.
- The server uses subscription auth, not API keys. Never reference
  `ANTHROPIC_API_KEY` in code or tests.
- `git push -u origin` requires the remote to be configured. If it fails,
  check `git remote -v` and report the issue.
- The `post_review` trigger means the code-review sub-agent will automatically
  review your diff after you finish. If it returns BLOCKER, the job goes to
  `awaiting_user` and the human must resolve it.
- If you need to create a database migration, use `alembic revision --autogenerate -m "<description>"`.

## Files this skill may update

- `src/**/*.py` (server code)
- `scripts/*.sh` (bootstrap, deploy scripts)
- `alembic/versions/*.py` (migrations)
- `.context/modules/*/CHANGELOG.md` (always)
- `.context/modules/*/CONTEXT.md` (when interfaces change)
- `tests/*.py` (new or modified tests)
