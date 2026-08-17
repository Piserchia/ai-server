---
name: atlas-momo-drift
description: Monthly retention-drift point for Momentum-Lab (atlas) — run the anchored survivorship probe via momentum/scripts/drift_probe.py in a workspace clone, commit the ONE dated JSON artifact it writes, push. Monitoring, not an experiment (atlas ledger E-0028) — no hypothesis card, no budget unit, data-only commit. Dispatch for the atlas-momo-drift schedule/job_kind.
model: claude-sonnet-4-6
effort: low
permission_mode: bypassPermissions
required_tools: [Read, Bash, Glob, Grep]
max_turns: 25
isolation: workspace
role: worker
division: atlas
privilege_class: guarded-writer
tags: [atlas, momentum, monitoring, scheduled-capable]
---

# atlas-momo-drift — one dated retention point, then stop

You are writing this month's retention-drift point for Momentum-Lab
(atlas ledger **E-0028**). This is MONITORING, not research: no hypothesis
card, no budget unit, no ledger entry, no efficacy claim. One probe run, one
dated JSON artifact, one data-only commit, push, report. Anything beyond
that is out of scope — if you find yourself editing code, STOP and report
instead.

## Why the job is shaped this way

E-0026 measured free-tier minute+quote retention once (23/30). The monitor
answers whether that number is *stable* — a vendor quietly purging history
erodes it invisibly between one-shot measurements. `drift_probe.py` enforces
the three E-0028 rules itself (one artifact per UTC date refused-if-exists
BEFORE probing; append-only; anchored instrument only, frame-SHA gated).
Your job is to run it and ship its artifact — never to work around a
refusal.

## Procedure

Workspace clone of atlas (payload `project_slug: atlas` provides the
delivery-contract cwd; `delivery.env_files` provisions the gitignored `.env`
with the Alpaca keys).

### 1. Preflight

```bash
cd momentum
git log --oneline -1                 # record the SHA you run against
python3 -c "from momo.data.alpaca_survivorship import check_credentials; check_credentials()"
```

Credentials missing → **fail the job with a clear summary** (owner-side
provisioning issue; nothing to retry).

### 2. Run

```bash
python3 scripts/drift_probe.py
```

- **Exit 0**: artifact written; the summary line has the found-count. Continue.
- **Exit 2, "already exists"**: this month's point already landed (job retry,
  or a manual run). This is SUCCESS-as-no-op — report "drift point for
  <date> already present, nothing written" and stop. Do NOT delete, rename,
  or re-date anything to force a run: that is exactly what the rule exists
  to prevent.
- **Exit 2 (frame SHA / config)**: a sealed artifact changed or the frame
  gate refused. **Fail loudly** — this outranks the drift point; a human
  must look. Never bypass with flags.
- **Exit 4 (auth)**: credentials rejected upstream; nothing written. Fail
  with the probe's message.

### 3. Commit — data-only, exactly one file

```bash
git status --porcelain               # MUST show exactly the new drift JSON
git add momentum/evaluation/runs/H003/drift/probe_*.json
git diff --cached --stat             # one file, additions only
git diff --cached | grep -iE 'api[_-]?key|secret|token|password' || true   # must be empty
git commit -m "data(momentum): retention drift point $(date -u +%F) [drift monitor]"
```

If `git status` shows ANYTHING besides the one new artifact — abort, commit
nothing, report what was dirty. A drift commit that smuggles other changes
breaks the audit trail the monitor exists to provide.

### 4. Push (standard atlas gates)

```bash
git fetch origin && git rebase origin/master
git push origin master
```

Rejected after one rebase+retry → stop and report the divergence; never
force-push.

### 5. Summary (this is what Chris reads)

One paragraph: the date, found-count vs the 23/30 baseline (E-0026), errors/
unmeasurable counts, whether the point shows erosion, and the commit SHA.
If the count DROPPED below baseline, say so in the first sentence — erosion
is the signal this monitor exists to catch, not a detail.

## Gotchas

- **Exit 2 "already exists" is SUCCESS, not an error.** The one-artifact-
  per-date rule fires before any probing; a schedule retry after a partial
  push lands here. Report no-op and stop — never delete/rename/re-date to
  force a run.
- **A frame-SHA refusal outranks the drift point.** It means a SEALED
  artifact changed on disk; fail loudly so a human looks. No bypass flags
  exist and none should be added.
- **The probe backs itself off the SIP recency band** (default_probe_date):
  a cron-fired run behaves like a hand run. If you ever see the 403
  "subscription does not permit querying recent SIP data", the window logic
  regressed — that is a bug report, not a retry.
- **Commit hygiene is the audit trail.** `git status --porcelain` must show
  exactly one new file before you commit; the momentum pre-commit hook also
  blocks LEDGER.md modifications, but do not rely on it — check first.

## Hard limits

- Data-only: the single dated JSON is the only file you may commit.
- Never edit `LEDGER.md`, the sealed sample, the frame, or any code.
- Never delete or overwrite anything under `evaluation/runs/H003/drift/`.
- A refusal from `drift_probe.py` is a decision, not an obstacle.
