---
name: app-patch
description: Patch an existing project to fix bugs or add features
model: claude-opus-4-7
effort: high
permission_mode: acceptEdits
required_tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
max_turns: 60
post_review:
  trigger: always
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: xhigh
tags: [projects, maintenance]
---

# App Patch

You are patching an existing project to fix a bug or add a feature. The project
lives at `projects/<slug>/` and is its own git repo (separate from the
ai-server repo). Changes are committed and pushed directly to main — no PR gate
for project repos.

## Inputs you will receive

Extract the project slug from the job description. Common patterns:

- "fix market-tracker: crypto dashboard shows NaN" -> slug is `market-tracker`
- "patch home-dash: add dark mode toggle" -> slug is `home-dash`
- Or look for `payload.project_slug` if set in the job payload.

If no slug is identifiable from the description or payload, use
`AskUserQuestion` once to ask which project to patch. Do not ask more than one
clarifying question; for anything else, make your best judgment and proceed.

## Protocol

Follow `.context/PROJECT_PROTOCOL.md` (in the ai-server root) for the
write-back protocol. The steps below are specific to app-patch.

## Procedure

1. **Orient.** Read the project's context files to understand what you're
   working with. Read all of these that exist:
   - `projects/<slug>/CLAUDE.md`
   - `projects/<slug>/.context/CONTEXT.md`
   - `projects/<slug>/.context/CHANGELOG.md` (last 3 entries only)
   - `projects/<slug>/skills/GOTCHAS.md`

   If the project directory does not exist at `projects/<slug>/`, stop
   immediately and report: "Project `<slug>` not found at `projects/<slug>/`."

2. **Read logs.** If the project has a `manifest.yml` with `type: service`,
   check the error log for clues:
   ```bash
   tail -50 volumes/logs/project.<slug>.err.log
   ```
   Also check the stdout log if the error log is empty or uninformative:
   ```bash
   tail -50 volumes/logs/project.<slug>.out.log
   ```

3. **Investigate.** Find the relevant code. Use `Grep` and `Glob` to locate
   the affected files. Read enough surrounding code to understand the context.
   Do not jump to fixing — understand the root cause first. If the issue
   description mentions a specific error message or behavior, search for that
   exact string in the codebase.

4. **Patch.** Make minimal, targeted changes. Follow these principles:
   - Prefer editing existing files over creating new ones.
   - Change only what is necessary to fix the bug or add the feature.
   - Preserve the project's existing code style and conventions.
   - If you need to add a dependency, note it explicitly in your summary.

5. **Test.**
   - For service-type projects: restart via `launchctl kickstart -k gui/$(id -u)/com.assistant.project.<slug>`, wait 3 seconds, then hit the healthcheck endpoint defined in `manifest.yml` under the `healthcheck` field.
   - For multi-service projects (check `manifest.yml` for a `services` array), each sub-service has its own launchd label: `com.assistant.project.<slug>-<service-name>`. Restart and healthcheck each one.
   - For static projects: verify file contents are correct by reading back the changed files.
   - If the project has a `test_command` in `manifest.yml`, run it.

6. **Check for secrets.** Before committing, scan the diff for leaked secrets:
   ```bash
   cd projects/<slug>
   git diff --cached | grep -iE 'api[_-]?key|token|secret|password'
   ```
   Also check unstaged changes:
   ```bash
   git diff | grep -iE 'api[_-]?key|token|secret|password'
   ```
   If any matches look like real credentials (not variable names or
   placeholders), **abort the commit** and report the finding. Do not push
   secrets.

7. **Commit and push.** This is a direct push to main — no PR gate for project
   repos (per user decision):
   ```bash
   cd projects/<slug>
   git add -A
   git commit -m "<concise subject describing the fix>"
   git push origin main
   ```

8. **Update docs.** Append an entry to the project's changelog:
   `projects/<slug>/.context/CHANGELOG.md`. Format:
   ```
   ## YYYY-MM-DD — <short description>

   **What broke / What was requested**: <one sentence>
   **What changed**: <list of files and what was done>
   **How to verify**: <one sentence>
   ```

9. **Summary.** Your final text message must be one paragraph covering: what
   was broken (or requested), what you changed, and how to verify the fix. This
   becomes the job's summary and the Telegram DM the user receives. Do not add
   meta-commentary like "I've completed the patch" — just state the facts.

## Quality gate (run this before your final text message)

Self-check before finishing:

- [ ] Changes are minimal and targeted — no unrelated refactoring
- [ ] No secrets in the diff (step 6 passed clean)
- [ ] Service restarts and passes healthcheck (if applicable)
- [ ] `projects/<slug>/.context/CHANGELOG.md` updated
- [ ] Changes committed and pushed to `origin main`

If any check fails, iterate. If after 3 iterations a check still fails, report
what could not be completed in your summary and set the issue aside for human
follow-up.

## Gotchas (living section — append when you learn something)

- **Separate git repo.** The project directory at `projects/<slug>/` is its OWN
  git repo, completely separate from the ai-server repo. Always `cd` into the
  project directory before any git operations. Never run `git` from the
  ai-server root when intending to commit project changes.
- **launchctl label format.** `launchctl kickstart` requires the full label:
  `gui/$(id -u)/com.assistant.project.<slug>`. Not just the slug.
- **Multi-service projects.** For projects like market-tracker that have
  multiple services, check `manifest.yml` for a `services` array. Each
  sub-service has its own launchd label:
  `com.assistant.project.<slug>-<service-name>`.
- **Healthcheck path.** The healthcheck URL path is in `manifest.yml` under the
  `healthcheck` field. Do not guess — read it.
- **Push failures.** If `git push` fails because the remote is ahead, pull
  first with `git pull --rebase origin main`, then push again. Do not force
  push.

## Files this skill updates as part of write-back

- Files within `projects/<slug>/` (the patch itself)
- `projects/<slug>/.context/CHANGELOG.md` (append entry)
- This file's `## Gotchas` section (only if you learned something reusable)
