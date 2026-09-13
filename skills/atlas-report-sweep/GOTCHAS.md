# atlas-report-sweep — Gotchas

## `enqueue_job` MCP tool is NOT wired up in this skill (2026-08-23 — RESOLVED 2026-09-12)

**RESOLVED (2026-09-12, retrospective f4e2fdea, proposal 636e79a0)**: the
`needs-dispatch-mcp` tag was added to the SKILL.md frontmatter, so the
runner now injects `mcp__dispatch__enqueue_job` for this skill. Fan-out
mode (step 2) works as designed; sequential fallback (step 3) is only
exercised if the MCP wiring itself breaks. Historical context preserved
below.

**Symptom**: sweep session runs, tries to fan out, and finds no
`mcp__dispatch__enqueue_job` tool. The skill's SKILL.md tells you to fall
through to sequential mode — but sequential is infeasible for the full 44+
target sweep in one session's budget.

**Root cause**: the MCP dispatch server is opt-in via the skill's
frontmatter `tags:`. `runner/session.py` (see comment "Skills opt in via
'needs-projects-mcp' / 'needs-dispatch-mcp' tags") only injects
`create_dispatch_mcp(job)` when `"needs-dispatch-mcp"` is present. The
`atlas-report-sweep` SKILL.md tags are `[atlas, finance, research,
scheduled-capable]` — no dispatch tag → no MCP tool.

**Dev-side fix** (must be committed in `~/Documents/repos/ai-server`, not
here): add `needs-dispatch-mcp` to the skill's frontmatter tags list:

```yaml
tags: [atlas, finance, research, scheduled-capable, needs-dispatch-mcp]
```

After deploy, the MCP tool will be present and step 2 of the skill's
Procedure works as designed.

**Runtime workaround** (what job 3e34cee8 did): call
`src.gateway.jobs.enqueue_job` directly from a scripted Python one-shot,
using the SAME queueing + deferred-dependency mechanics the MCP tool
wraps. Skeleton lives at `/tmp/atlas_sweep_dispatch_3e34cee8.py` in
that session's trace — the shape is:

1. `enqueue_job("atlas-report: asset <SYM>", ...)` per holding — queued
   immediately, runner drains in parallel.
2. Insert `Job(status=deferred, payload={"depends_on": [...asset ids]})`
   directly for each sector (crypto set = BTC/ETH/HYPE/LINK/ONDO/SOL/
   USDC/XRP; stock set = all others).
3. Insert a portfolio-brief deferred Job depending on assets + sectors.

The runner's `plans.py` promotes deferred rows once every dependency
reaches a terminal state — same behaviour as the MCP tool's
`depends_on=[...]` path.

**Why not just do sequential?** 44 assets × ~5-15 minutes per report ×
one session budget = impossible. The skill explicitly notes fan-out is
"preferred" for a reason — each target gets its own budget/charter/eval
loop and failures stay isolated.

## Simpler HTTP fallback: POST /api/jobs (2026-09-07)

If the MCP dispatch tool is missing and you don't want to write a
`src.gateway.jobs` python one-shot, `curl -X POST
$BASE/api/jobs -H "Authorization: Bearer $WEB_AUTH_TOKEN"` with
`{"description": "atlas-report: asset <SYM>", "kind": "task"}` enqueues
each target as an independent runner job — same isolation, same
per-target budget. Trade-off: the HTTP endpoint has no `depends_on`
field, so ordering relies on FIFO + `max_concurrent_jobs=4`
draining. Enqueue in **assets → sectors → portfolio** order; the last
sector/portfolio jobs will start after ~34/4 batches of assets, so most
assets finish first. `latest_suggestion` for any still-running asset
falls back to prior-week values (mildly stale, not wrong). If you need
strict ordering, use the deferred-row workaround above instead.

Env gotcha: don't `source .env` — the file has unquoted paths with
spaces on later lines that zsh chokes on. Just `export
WEB_AUTH_TOKEN=…` and `WEB_PORT=8080` directly.
