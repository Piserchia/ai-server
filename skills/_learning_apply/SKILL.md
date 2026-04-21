---
name: _learning_apply
description: Internal skill. Appends a learning proposal (from the learning extractor) to the correct module's skills/<CATEGORY>.md file. Not user-triggerable.
model: claude-sonnet-4-6
effort: low
permission_mode: bypassPermissions
required_tools: [Read, Edit, Bash]
max_turns: 6
tags: [internal, learning]
---

# Learning apply (internal)

The runner's learning extractor classified a completed job and identified a
reusable learning. Your only job is to append it to the right file. Nothing
else.

## Payload you will receive

- `module`: one of the installed modules under `.context/modules/` (e.g., `runner`, `gateway`, `db`, `registry`, `hosting`) or `project`
- `category`: exactly one of `GOTCHA`, `PATTERN`, `DEBUG`
- `title`: the learning's title (<= ~80 chars)
- `content`: the markdown body (2-6 sentences, already written)
- `evidence_job_id`: the parent job's 8-char id prefix
- `parent_job_id`: the parent job's full UUID (for audit log link)

## Procedure

### 1. Resolve the target file

```
target = .context/modules/<module>/skills/<CATEGORY>.md
```

Examples:
- `module=runner, category=GOTCHA` → `.context/modules/runner/skills/GOTCHAS.md`
- `module=gateway, category=DEBUG` → `.context/modules/gateway/skills/DEBUG.md`
- `module=registry, category=PATTERN` → `.context/modules/registry/skills/PATTERNS.md`

Note the singular → plural mapping:
- `GOTCHA` → `GOTCHAS.md`
- `PATTERN` → `PATTERNS.md`
- `DEBUG` → `DEBUG.md`

If `module == "project"`, the learning is project-scoped, not server-scoped.
For now, skip applying — log a note and exit. Project-level learning application
is a future enhancement (no project skills/ hierarchy exists yet).

### 2. Verify the file exists

```bash
ls -la .context/modules/<module>/skills/<FILENAME>
```

If it doesn't exist, run `bash scripts/seed-module-skills.sh` first to bootstrap
it (idempotent; preserves any existing content). Then verify again.

### 3. Read the current content and find the APPEND marker

```bash
grep -n "APPEND_ENTRIES_BELOW" .context/modules/<module>/skills/<FILENAME>
```

The seed script places `<!-- APPEND_ENTRIES_BELOW -->` on its own line near the
top. All new entries go directly AFTER that marker so newest appears first.

If the marker is missing (a human may have edited the file), just append at
the end of the file; don't try to reconstruct the marker.

### 4. Construct the new entry

Format:

```markdown
## YYYY-MM-DD — <title>

<content>

_Evidence: job `<evidence_job_id>`_
```

Where:
- `YYYY-MM-DD` is today's date in UTC (`date -u +%F`)
- `<title>` is the title from payload
- `<content>` is the content from payload, rendered as-is (it's already markdown)
- `<evidence_job_id>` is the 8-char parent job id

### 5. Insert after the marker

Use the `Edit` tool to insert the new entry immediately after the
`<!-- APPEND_ENTRIES_BELOW -->` line. Preserve all existing content.

Concretely: find the line `<!-- APPEND_ENTRIES_BELOW -->` and replace it with:

```
<!-- APPEND_ENTRIES_BELOW -->

<new entry content here>
```

This preserves the marker so the next learning lands in the same place.

### 6. Commit

```bash
git add .context/modules/<module>/skills/<FILENAME>
git commit -m "learn(<module>/<CATEGORY>): <title>

From job <evidence_job_id> via learning extractor."
```

Do NOT push — commits accumulate locally; humans push when reviewing.

### 7. Final text

One sentence confirming the file updated and the commit hash.

## Hard rules

- Modify ONLY the target skills/<CATEGORY>.md file. No other files.
- Do NOT reword the `content` — it came from the classifier already. Preserve verbatim.
- Do NOT duplicate an existing entry. Before writing, grep for the title (case-insensitive). If it already exists, log a note and exit; do not append.
- Do NOT modify the `<!-- APPEND_ENTRIES_BELOW -->` marker or the file header.

## Gotchas

- The file may end without a trailing newline in some git configs. When
  inserting, make sure there's a blank line between your new entry and
  the previous entry.
- If two `_learning_apply` jobs run concurrently on the same file, the
  second commit may have a merge conflict. The current design enqueues
  these serially (runner concurrency=2, but learnings land on different
  module files typically). If conflicts become common, we'll add a lock.
