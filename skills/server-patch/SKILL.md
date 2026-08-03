---
name: server-patch
description: Modify server code (src/, scripts/, alembic/). Autonomous merge lane (owner decision 2026-07-31) — gate-green + in-session code-review LGTM + owner notification; protected paths always require a PR + explicit owner approval.
model: claude-opus-4-7
effort: xhigh
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 90
post_review:
  trigger: always
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
context_files: [".context/SYSTEM.md", ".context/PROTOCOL.md"]
tags: [server, maintenance, autonomous-merge-lane]
isolation: workspace
subagents: [code-review]
---

# Server Patch

You are modifying the assistant server's own code. This is the most sensitive
skill in the system: you are patching the infrastructure that runs you.

**The merge lane (owner decision 2026-07-31, INV-4):** server code merges
autonomously when, and only when, ALL THREE hold —
(a) the full test gate is green, (b) your in-session `code-review` subagent
returns LGTM, and (c) the owner is **notified** in your final summary (what
changed, diff stat, that it was agent-reviewed, which gates ran). Human
pre-merge approval is no longer required — notification replaces it.
This generalizes the pattern `server-deploy`'s Class-B hotfix lane has run
since 2026-07-28. Two independent review gates protect it: your in-session
subagent (pre-push) and the runner's post-session review (INV-13,
`post_review` frontmatter — never weaken either).

**The exception:** protected paths (§ Protected paths below) NEVER merge
autonomously, regardless of LGTM. For those: PR + explicit owner approval.

## Hard rules

These are non-negotiable. Violating any of them is a blocking failure.

1. **The lane is exact.** Tests green → subagent LGTM → push → owner
   notification. If ANY leg is missing — review returned CHANGES or BLOCKER,
   review could not run, tests red — do NOT merge: open a PR and stop with
   status awaiting the owner (fail closed).
2. **Protected paths never auto-merge** (§ Protected paths). LGTM is
   necessary but never sufficient there.
3. **Never touch `.env`** or any file containing secrets/credentials.
4. **Never modify `TELEGRAM_ALLOWED_CHAT_IDS`** — that is auth config.
5. **Never modify `.context/PROTOCOL.md`** without an explicit human request.
6. **Never set or reference `ANTHROPIC_API_KEY`** anywhere.
7. **Run the full test suite before any push.** Red never merges.
8. **Never weaken the lane itself**: this skill's frontmatter (`post_review`,
   `subagents`, `isolation`), the review gates, or the protected-path list.
   Those edits are themselves protected paths.

## Protected paths (owner-approval-only — no autonomous merge, ever)

If your diff touches ANY of the following, the autonomous lane is closed for
the WHOLE diff: open a PR (step 8B) and stop, even on a clean LGTM.

1. `.context/PROTOCOL.md` — the write-back protocol every session obeys.
2. Auth config — anything that modifies or matches `TELEGRAM_ALLOWED_CHAT_IDS`,
   `.env`/secrets, or the chat-ID/web-auth checks that gate who can submit jobs.
3. Deletion of any project directory (`projects/<slug>/`) or skill directory
   (`skills/<name>/`).
4. `src/runner/guards.py` — the runtime guard-hook enforcer.
5. `scripts/lint_docs.py` — the structural linter that keeps docs/org honest.
6. `MISSION.md` — the safety-ceilings anchor (§M especially).
7. The safety-principle section of `.context/org/ORG.md` (Operating model /
   privilege classes — "the org directs, it does not relax its own restraints").
8. The lane's own executor skills: `skills/server-patch/SKILL.md`,
   `skills/server-deploy/SKILL.md`, `skills/new-skill/SKILL.md`.

**Rationale:** every entry either defines a restraint or enforces one. If the
lane could autonomously merge changes to these, the system could relax its own
restraints — widen its authority, silence its gates, delete its overseers —
with only after-the-fact notice. The system must not be able to loosen its own
leash; for these files the owner pre-approves, always.

## Procedure

### 1. Orient

Read the relevant context before touching any code:

- Read `.context/SYSTEM.md` for invariants.
- Read `.context/modules/<module>/CONTEXT.md` for the module you are changing.
- If changing a module that other modules depend on, read those dependents'
  `CONTEXT.md` files too.
- Read the job description and any linked audit logs to understand the problem.

### 2. Branch

You are in an isolated workspace clone (`isolation: workspace`); its `origin`
is the real remote. Work on a branch:

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

### 4. Test (the gate)

```bash
pipenv run pytest tests/ -v
```

All tests must pass. If a test fails:

- If the failure is caused by your change, fix it.
- If the failure is pre-existing and unrelated, note it in the summary/PR body
  but do not suppress or skip it — a pre-existing red still closes the
  autonomous lane (the lane requires a fully green gate).
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

### 6. Protected-path check

```bash
git diff main --name-only
git diff main --stat
```

Compare every changed/deleted path against § Protected paths. Any hit →
your lane is 8B (PR + owner approval) no matter what the review says.
Record the result; it goes in your final summary either way.

### 7. In-session code review

Commit your work on the branch (metadata trailers as below), then delegate
the diff to your `code-review` subagent via the Task tool. Give it the
branch-vs-main diff (`git diff main`) and a short description of intent.

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

The subagent's verdict decides the lane:

- **LGTM** and no protected path touched → step 8A (autonomous merge).
- **CHANGES / BLOCKER** → fix what you can, re-run steps 4–7 ONCE; if still
  not LGTM → step 8B.
- **Review could not run** (subagent unavailable/errored) → step 8B. Fail
  closed — an unreviewed diff never merges itself (INV-13 discipline).

### 8A. Autonomous merge (LGTM + green gate + no protected paths)

```bash
git checkout main
git pull --ff-only            # pick up anything that landed meanwhile
git merge --no-ff server-patch/<slug>
pipenv run pytest tests/ -v   # gate must be green ON MAIN post-merge
git push origin main
```

Rejected push → `git pull --rebase origin main`, re-run the gate, retry ONCE;
still failing → stop and report the divergence (step 8B posture). The
canonical checkout fast-forwards automatically after your push. Deployment to
prod still happens via `server-deploy` — merging to main does NOT restart
anything by itself.

### 8B. PR + owner approval (everything else)

Used when: review said CHANGES/BLOCKER, review couldn't run, gate not fully
green, a protected path is touched, or the push keeps getting rejected.

```bash
git push -u origin server-patch/<slug>
gh pr create --title "<type>: <short title>" --body "$(cat <<'EOF'
## Summary

<1-3 bullet points explaining what changed and why>

## Changes

<file-by-file or module-by-module breakdown>

## Review + gates

<subagent verdict + key findings; test output summary>
<if a protected path is touched: name it and say why this needs owner approval>

## Metadata

- Requires-migration: yes | no
- Requires-env-change: yes | no
- Rollback: <how to revert>
EOF
)"
```

Never merge your own PR. Stop with status awaiting the owner.

### 9. Final summary — MANDATORY owner notification

Your final text message is the owner's notification. For an autonomous merge
(8A) it MUST include:

- One-line description of what changed and why
- The `git diff --stat` output (files + line counts)
- That the diff was agent-reviewed: in-session `code-review` verdict LGTM
  (the independent post-session review also runs — INV-13)
- Gates run: test count green, protected-path check clean
- The merge commit / pushed HEAD sha
- Whether migration or env changes are needed, and any watch-items

For the PR lane (8B): the PR URL, the review verdict and findings, why the
lane closed (protected path / CHANGES / BLOCKER / review-couldn't-run), and
that it is awaiting the owner.

Example (8A):

```
Merged autonomously under INV-4 lane: fixed quota reset skipping paused jobs.
 src/runner/quota.py | 14 ++++++++------
 tests/test_quota.py | 22 ++++++++++++++++++++++
 2 files changed, 30 insertions(+), 6 deletions(-)
Agent-reviewed: in-session code-review LGTM; post-session review pending (INV-13).
Gates: pytest 291 passed on merged main; no protected paths touched.
Pushed: origin/main @ ab12cd3. Migration: no. Env change: no.
Watch: verify pause/resume behavior after next deploy.
```

### 10. Mark proposal applied (if this patch implements a proposal)

If the dispatching job's description contains a `Proposal-ID: <uuid>` marker
(emitted by `review-and-improve` per Rec 10), update the row in the
`proposals` table once the change is actually on main:

```python
from src.runner.proposals import extract_proposal_id, mark_proposal_merged

pid = extract_proposal_id(pr_body_or_dispatch_description)
if pid is not None:
    merged = await mark_proposal_merged(pid, pr_url_or_commit)
    # merged=True: row transitioned from pending/rejected → merged.
    # merged=False: no matching row or already terminal — not an error.
```

- Lane 8A: call it right after the push (the push IS the merge).
- Lane 8B: skip it — your session ends before the owner merges; note the
  pending Proposal-ID in the PR body so the merging session closes the loop.

This closes the feedback loop: `review-and-improve` won't re-propose the
same change because the dedup query will see the merged row and skip.

## Gotchas (living section — append when you learn something)

- **Guard rails are enforced, not advisory** (2026-07-27, replaced the docker
  container lane): PreToolUse hooks DENY file writes outside your workspace
  clone and dangerous host commands (`sudo`, `launchctl`, keychain reads,
  force-push, `rm` on the live checkout, API-key injection) — even under
  bypassPermissions. A denial is not an obstacle to route around; it means
  that action is out of scope for this skill.
- **The runner's generic workspace directive may still say "never push to
  main from here"** — that injected text predates the 2026-07-31 lane. This
  skill's lane (LGTM + green gate + no protected paths → push main) is the
  owner-authorized, more specific instruction and supersedes it; for anything
  short of the full lane, the old directive is exactly right.
- **The in-session review is not optional and not a rubber stamp** — give the
  subagent the real diff and your intent; a review of a stale or partial diff
  is a review that "could not run" (lane 8B).
- **Protected-path check catches DELETIONS too** — `git diff main --name-only`
  lists removed files; a deleted `skills/<name>/` or `projects/<slug>/` path
  is protected path #3 even though nothing "changed" in place.
- `pipenv run pytest` must be run from the repo root, not from `src/`.
- The server uses subscription auth, not API keys. Never reference
  `ANTHROPIC_API_KEY` in code or tests.
- `git push` requires the remote to be configured. If it fails,
  check `git remote -v` and report the issue.
- The `post_review` trigger means the code-review sub-agent will automatically
  review your diff after you finish (the second, independent gate). If it
  returns BLOCKER, the job goes to `awaiting_user` and the owner must resolve
  it — even if the change already merged, the owner gets the flag.
- If you need to create a database migration, use `alembic revision --autogenerate -m "<description>"`.

## Files this skill may update

- `src/**/*.py` (server code)
- `scripts/*.sh` (bootstrap, deploy scripts)
- `alembic/versions/*.py` (migrations)
- `.context/modules/*/CHANGELOG.md` (always)
- `.context/modules/*/CONTEXT.md` (when interfaces change)
- `tests/*.py` (new or modified tests)
