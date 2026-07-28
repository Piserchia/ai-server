# System Evaluation — 2026-07-28

> Full-system gap audit against the two operating goals: **(1) host projects
> well** and **(2) execute complex project creation + deployment**. Conducted
> via four parallel deep-dives (deployment/ops, interfaces, testing/reliability,
> project-lifecycle/docs) cross-checked against the live production system.
> This doc is the living tracker; the "Status" column is updated as items land.

## Verdict

The **control plane is well-built** (job/skill/contract model, single-writer
topology, guard hooks, ff-only deploy gates, the delivery-contract machinery).
Gaps cluster at the **edges**: disaster recovery, steady-state ops, UI depth,
testing of every I/O path, and a half-migrated dev-repo topology whose consumers
weren't updated with it. Several problems are **invariants the docs claim are
enforced but aren't**.

## Status legend

`TODO` not started · `WIP` in progress · `DONE` fixed this pass · `USER` needs
an owner-run production command · `WONTFIX` intentionally deferred.

## Top blockers (ranked against the two goals)

| # | Blocker | Sev | Status |
|---|---|---|---|
| B1 | Production runs stale code — prod pinned behind origin/main by the entire SDK-migration + segregation work; no auto-deploy, no drift indicator | crit | USER (deploy) + DONE (drift indicator) |
| B2 | Restore is non-functional: wrong DB name (`aiserver` vs `assistant`) + can't stop launchd writers | crit | DONE (skill) |
| B3 | Off-site backup has never run; `projects/` + content projects not backed up at all | crit | USER (R2) + DONE (alert-when-unconfigured) |
| B4 | Dev-repo topology shipped ahead of consumers: `app-patch`/`_evaluate`/templates still assume in-place → first dev-repo project breaks update+verify | crit | WIP (Batch 3) |
| B5 | "Create AND deploy" has no deploy leg: `plan` never decomposes to `project-redeploy`; `app-patch` no hand-off; human-approval deploy dead-ends | crit | WIP (Batch 3) |
| B6 | market-tracker (retired) dangling — manifest + DB row persist → `healthcheck failed=3` forever, real outages indistinguishable | major | USER (DB row) + DONE (repo) |
| B7 | Documented invariants not enforced: INV-8 (cancel dies on bad payload), INV-9 (no status guard), INV-13 (review fails open), INV-14 (convention-only) | major | DONE (8/13) + doc-corrected (9/14) |
| B8 | UIs view-only + misleading: phantom `/cancel` `/rate` `/status` commands; no job-detail/log/live view; failures notified without reasons | major | TODO (UI backlog) |

## Findings by area

### Documentation
- D1 `README.md` / `GETSTARTED.md` frozen at "Phase 2, 52 tests"; predate SDK-native + dev-repo model. **DONE**
- D2 SYSTEM.md claims a `/proposals` Telegram command + telegram→proposals dependency that don't exist; claims INV-9/13 enforcement that doesn't exist. **DONE**
- D3 `audit_log.py` documents a `cost_usd` event field never written. **DONE**
- D4 `TEARDOWN.md` describes the wrong (old docker/ollama) system + contains a plaintext revoked GitHub PAT. **DONE**
- D5 `server-upkeep` skill still probes the removed container lane + runs a broken `SELECT status FROM projects`. **DONE**

### Deployment / operations
- O1 No rollback / version pinning; `alembic upgrade` runs before the pytest gate. **DONE (skill: migrate-after-gate + rollback note)**
- O2 Backup + healthcheck launchd timers installed by no script (hand-created) → absent on a rebuild. **USER (install script added)**
- O3 `register-project.sh` not idempotent (bounces live services every run; half-registered state on failure). **TODO**
- O4 External heartbeat worker deployment unverified. **USER (wrangler check)**
- O5 Deploy/ops skills run `bypassPermissions` + `isolation: none` on the real checkout — de-facto host-tier, outside the guard net (INV-18 assurance is partial). **TODO (documented)**

### User interface
- U1 Bot advertises `/cancel` `/rate` `/status <id>` — none registered (silent no-ops). **DONE**
- U2 No rendered job-detail / audit-log view; SSE stream endpoint has no client despite SYSTEM.md claim. **TODO (backlog)**
- U3 Failure notifications carry no reason; task failures silent through 3 retries. **TODO (backlog)**
- U4 No cost/usage/duration surfaced anywhere. **TODO (backlog)**
- U5 No project logs/restart/deploy-status from either UI; tasks invisible on web. **TODO (backlog)**
- U6 `_job_to_chat` in-memory → bot restart drops a `/chat` answer. **TODO (backlog)**
- U7 `/clear` sets `cancelled` without publishing a cancel (session keeps running); hardcodes `"jobs:queue"`. **DONE**

### Testing / reliability
- T1 No integration harness; `fakeredis` installed but used by zero tests; `main.py`/`session.py` zero behavioral coverage. **WIP (Batch 4)**
- T2 Quota detect/pause/resume untested (largest blast radius). **DONE (Batch 4)**
- T3 Migrations never exercised; no drift check; no DB constraints (INV-14). **DONE (Batch 4: upgrade+drift smoke)**
- T4 Plan-DAG promote/cascade swallow exceptions → return 0 → task hangs silently. **DONE (Batch 2: distinguish failure)**
- T5 `_update_task_after_job` log-and-continue → task silently stalls. **TODO**
- T6 `sync_canonical` violates "never raises" on git timeout → successful job marked failed. **DONE (Batch 2)**
- T7 Cancel listener no per-iteration guard (INV-8). **DONE (Batch 2)**
- T8 No per-async-task supervision; dead scheduler/cancel-listener invisible; `is_paused` Redis read outside heartbeat guard. **DONE (Batch 2)**

### Other (correctness + security)
- X1 `config.py` `server_root` default wrong (`.../assistant`, missing `-server`). **DONE (Batch 2)**
- X2 atlas manifest lists `ANTHROPIC_API_KEY` in `env_required` (nuance: atlas is a separate hosted project; still a boundary worth a conscious decision). **USER (owner decision)**
- X3 Live secrets (`.env`, `~/.cloudflared/*.json`, retired `market-tracker/.env` with a real key) on-disk only, uninventoried. **USER**
- X4 Content projects (`research-deep`, `ideas`) have no off-site git remote; `ideas/history.jsonl` is 0 bytes (idea-generation never committed). **USER**

## Production-side actions (owner-run — see the session's command list)

Deploy the pushed code; delete market-tracker's DB row; configure R2 (or accept
the alert-when-unconfigured change); run the new timer-install script; verify the
heartbeat worker. Exact commands provided separately.
