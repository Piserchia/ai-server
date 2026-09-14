# alpha-intake gotchas

- (2026-09-14, design) Read-only by construction: a router-created job
  has no project_slug payload, so a workspace-isolated intake would
  clone the AI-SERVER repo, not atlas — that is why filing belongs to
  the dispatched FILE-mode alpha-research job, which carries the slug
  in its payload.
- (2026-09-14, design) Plain-text Telegram messages go through
  triage_plain_text; a very short "alpha: X" can be triaged to chat
  instead of a task job. `/task alpha: <idea>` is the deterministic
  path; mention it to the owner if an idea seems to have vanished.
