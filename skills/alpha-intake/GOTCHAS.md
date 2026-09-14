# alpha-intake gotchas

- (2026-09-14, design) Read-only by construction: a router-created job
  has no project_slug payload, so a workspace-isolated intake would
  clone the AI-SERVER repo, not atlas — that is why filing belongs to
  the dispatched FILE-mode alpha-research job, which carries the slug
  in its payload.
- (2026-09-14, corrected at final review) Plain-text "alpha: ..." messages
  are safe: triage_plain_text consults the rule router FIRST, and the
  alpha rule sits at the top of _RULES, so any "alpha:"-prefixed message
  becomes a task job. The real front-door hazard was rule ORDERING
  (plan-rule connectives like "and then" used to hijack prefixed ideas —
  fixed 2026-09-14 by moving the alpha rule first).
