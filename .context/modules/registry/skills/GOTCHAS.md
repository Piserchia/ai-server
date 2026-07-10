# Gotchas

> **What this file is for**: Non-obvious traps, unexpected behaviors, and things that look like they should work but don't.
>
> **When to add an entry here**: When a session hit a trap — something implicit, an ordering requirement, a race condition, an environment-specific behavior — that a future session should know about before making similar changes.
>
> Append entries newest-first. Each entry should include a date header,
> the symptom or pattern, the fix or approach, and (when possible) a
> reference to the audit log that led to the finding.
>
> This file is seeded empty. Claude sessions working in this module should
> append here when they learn something reusable (see `.context/PROTOCOL.md`).

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->

## 2026-07-09 — gh repo archive fails silently without repo ownership

`gh repo archive <owner>/<repo>` exits 0 and prints nothing when the authenticated account lacks owner permissions on the repository — it does not archive the repo and does not surface an error. The alfredbot service account cannot archive repos owned by other GitHub users or orgs. When retiring a project, add a manual step in the job summary noting the human owner must run `gh repo archive` from their own account or via the GitHub UI.

_Evidence: job `7403d5a7`_
