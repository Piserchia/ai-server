---
name: _writeback
description: Internal skill. The runner spawns this after any session that modified files without updating a CHANGELOG.md. Not user-triggerable.
model: claude-sonnet-4-6
effort: low
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 6
tags: [internal, write-back]
---

# Write-back follow-up

A previous session in this directory modified files but did not update any
`CHANGELOG.md`. Your only job is to do that write-back now. Nothing else.

## Context you will receive

The runner will prepend a `# Prior session` block to your prompt containing:
- The job ID of the session that just finished
- `git diff --stat` of what it changed
- The final text it produced (the summary)

## Procedure

1. Run `git status --porcelain` to see what's modified and where.
2. For each affected module under `src/` or each affected project under
   `projects/<slug>/`, open the relevant `CHANGELOG.md` and append an entry
   in the format from `.context/PROTOCOL.md`:

   ```markdown
   ## YYYY-MM-DD — <short summary from the prior session>

   **Agent task**: <what the prior job was asked to do>
   **Files changed**:
   - `path/to/file.py` — <what changed>

   **Why**: <reasoning; take from the prior session's summary>
   **Side effects**: <if known; otherwise "None observed">
   **Gotchas discovered**: <if the prior session's summary mentions any>
   ```

   **"Why" quality gate (Rec 13):** The **Why** field must not be empty or
   generic. If the prior session's summary is too thin to reconstruct
   reasoning (e.g., just "fixed bug"), read the audit log at
   `volumes/audit_log/<prior_job_id>.jsonl` to understand what files the
   session touched and in what order. Use tool_use events (Read, Edit,
   Write, Bash) to reconstruct the likely reasoning. Acceptable "Why"
   entries explain the root cause or motivation, not just the action:
   - Bad: "Changed foo.py"
   - Bad: "Fixed the bug"
   - Good: "Changed foo.py because the bar check silently returned True
     when the input was None, causing the downstream validator to skip
     validation entirely"

3. If any module's `CONTEXT.md` is stale because of the prior session's
   changes — i.e., the public interface changed — update `CONTEXT.md` too.
   If unsure, don't touch it.

4. Commit ONLY the CHANGELOG/CONTEXT updates. Do not touch the prior
   session's code changes.
   ```bash
   git add -A
   git commit -m "Write-back for <prior_job_id[:8]>"
   ```

5. Your final text: one sentence confirming which CHANGELOG(s) you updated.

## Hard limits

- Do not modify any `.py`, `.yml`, `.yaml`, `.sh`, or other non-documentation
  file. If the prior session's code is wrong, that's a job for `app-patch` or
  `self-diagnose`, not for you.
- Do not revert or amend the prior session's work.
- If there's no clear match between the modified files and any module's
  CHANGELOG (e.g., the prior session modified something outside known
  modules), log a note to `volumes/audit_log/<your_job_id>.jsonl` via your
  final text block and exit — do not improvise a new CHANGELOG location.

## Why this skill exists

Write-back by the original session is the rule (see `.context/PROTOCOL.md`).
This skill is the fallback when the rule wasn't followed. Frequent triggering
of this skill is a signal that the primary skill's SKILL.md needs clearer
write-back instructions — that's something `review-and-improve` watches for.
