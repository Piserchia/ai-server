---
name: project-update-poll
description: Run a project's configured update command. Cheap, fast, fail-silent.
model: claude-haiku-4-5-20251001
effort: low
permission_mode: bypassPermissions
required_tools: [Read, Bash]
max_turns: 4
context_files: [".context/PROJECTS_REGISTRY.md"]
tags: [scheduled, per-project, cheap]
---

# Project Update Poll

You run a project's configured `on_update` command and report the result. This
is a cheap, fast, fail-silent skill designed for scheduled polling -- it does
not attempt diagnosis or repair on failure.

## Inputs you will receive

Extract from `payload`:
- **project_slug** (required): the slug of the project to poll (matches a
  directory under `projects/`)

If `payload.project_slug` is missing, return an error message immediately:
"Error: project_slug is required in payload. Cannot poll without a target project."

## Procedure

1. **Validate the project exists.** Check that `projects/<slug>/` exists.
   If not, return: "Error: project '<slug>' not found under projects/."

2. **Read the manifest.** Read `projects/<slug>/manifest.yml`. Look for the
   `on_update` section. Expected format:
   ```yaml
   on_update:
     command: "<shell command to run>"
     timeout: 120  # optional, seconds, default 120
   ```

3. **No update configured?** If `manifest.yml` doesn't exist or has no
   `on_update` section, return: "No update configured for '<slug>'; no-op."
   This is a normal, expected outcome -- not an error.

4. **Run the command.** Execute `on_update.command` with the working directory
   set to `projects/<slug>`. Respect the timeout (default 120s).

5. **Capture output.** Record stdout and stderr. Write them to the audit log
   as part of the job's normal output.

6. **Handle result.**
   - **Exit 0**: Return a success message: "Poll '<slug>': OK. <first line of stdout if any>"
   - **Nonzero exit**: Wait 60 seconds, then retry the same command once.
     - If retry succeeds (exit 0): "Poll '<slug>': OK after retry."
     - If retry also fails: Log the failure and return:
       "Poll '<slug>': FAILED (exit <code>). stderr: <last 3 lines>. Giving up."
       Do **not** enqueue a `self-diagnose` job -- this skill is too cheap to
       justify the cost of diagnosis for a polling failure.

## Hard rules

- **No diagnosis on failure.** This skill exists to be cheap. If the command
  fails twice, log it and move on. The `server-upkeep` daily audit will catch
  persistent failures.
- **One retry only.** Do not retry more than once.
- **Respect timeout.** Kill the command if it exceeds the configured (or
  default 120s) timeout.
- **No modifications.** This skill reads manifest.yml and runs a command. It
  does not modify any project files, configuration, or state.

## Gotchas (living section -- append when you learn something)

- **No `on_update` is normal**: most projects won't have this configured.
  Returning "no-op" is the happy path for those projects.
- **Long-running commands**: some update commands (e.g., pulling large repos,
  rebuilding containers) may take longer than 120s. The manifest can override
  the timeout, but check it.
- **Environment**: the command runs in the project's directory but inherits
  the runner's environment. If the command needs specific env vars, those
  should be in the project's own `.env` (which the command should source).

## Files this skill updates as part of write-back

None. This skill is read-only by design -- it only runs a command and reports
the result. No CHANGELOG update, no file modifications.
