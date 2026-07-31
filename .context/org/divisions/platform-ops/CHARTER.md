# Charter — Platform Ops division

**Manager:** `ops-manager`
**Charter (goal):** the server stays healthy, deploys are safe, and failures are
detected and recovered fast. "You don't have to think about the server for a
week" (MISSION Phase-5 done-criterion). Own server code changes, the deploy
pipeline, DR, and incident response.

## Roster

| Agent | Role | Privilege | Purpose |
|---|---|---|---|
| `ops-manager` | manager | read-only | Weekly ops review: health/deploy/DR gaps → proposals |
| `server-patch` | worker | guarded-writer | Modify server code (PR-gated, code-review LGTM, manual merge — INV-4/13) |
| `server-deploy` | worker | prod-operator | **Self-healing** dev→prod: ff-only pull, migrate-safe, test gate, seed schedules, restart — AND fixes on the go (operational autonomously; code fixes born in the dev repo, re-gated, `code-review`-LGTM'd + owner-notified before deploy). The gate is never bypassed |
| `server-upkeep` | worker | prod-operator | Daily 3am: log rotation, VACUUM, health audit, anomaly DM |
| `restore` | worker | prod-operator | DR restore from backup (terminal/god only — stops the runner) |
| `self-diagnose` | worker | prod-operator | Incident response: read audit/service logs, apply low-risk fixes |
| `deploy-director` | worker | read-only | Summary-first deploy dispatch: derives the pending-range summary, preflights, risk-classifies, dispatches the gated executor with the summary attached, verifies post-conditions. Directs; never executes a deploy |

## Standards

- Red gate never reaches prod (tests/build/healthcheck). Migrations validated on
  a throwaway DB + snapshot before the live upgrade (server-deploy §2).
- Server code never auto-merges (INV-4) — **except** the owner-authorized
  deploy-hotfix lane: `server-deploy`'s Class-B fixes push a `code-review`-LGTM'd,
  gate-green fix to main + notify the owner (no human pre-merge), ON THE DEPLOY
  PATH ONLY. Normal `server-patch` still requires human merge. `code-review` must
  LGTM either way (INV-13). This is the sharpest autonomy in the system and the
  #1 reason the `prod-operator` guardrail (P4) matters.
- DR must actually work: `restore` targets DB `assistant`; off-site backup is a
  standing concern until R2 is configured (EVALUATION_2026-07-28 B2/B3).
- `prod-operator` agents run with the most reach and least containment today —
  the division's top enhancement target is the privilege guardrail (design doc P4).
- **Subscription economics is owned here** (MISSION § K): quota-pause frequency,
  job-volume trends, and model-tier spend hygiene are ops-manager audit items.
- **The user-facing surface (Telegram bot + web gateway) is owned here as
  infrastructure** (CEO 2026-07-30 finding #8, owner-adopted): availability,
  error rates, and health of `gateway/telegram_bot` + `gateway/web`. Product/UX
  evolution of the surface routes through the CEO.
- **The `server-deploy` self-healing lane is audited weekly** by ops-manager:
  every Class-B fix must show commit + code-review LGTM + owner notification.

## Cadence

Weekly (ops review). Event: 2 failures in the same ops skill / 10 min → self-diagnose.

## Feedback / reports

Reads division-scoped job outcomes + `docs/EVALUATION_*` + `docs/TROUBLESHOOTING.md`;
writes `REPORT.md`.
