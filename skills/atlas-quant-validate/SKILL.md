---
name: atlas-quant-validate
description: "Weekly quant validation desk — run the quantlab stack over the strategy roster (costed backtest -> metrics -> walk-forward judged on the WORST fold -> 8-check leakage critic -> Deflated Sharpe vs lifetime trial N) producing R-#### reports + a health pass on prior PASSes, commit + push artifacts, Telegram TL;DR. Reports only, no order path ever. Dispatch for the atlas-quant-validate schedule/job_kind, or on demand (\"run the quant sweep\")."
model: claude-opus-5
effort: high
escalation:
  on_failure:
    model: claude-opus-5
    effort: xhigh
permission_mode: bypassPermissions
required_tools: [Read, Write, Edit, Bash, Glob, Grep]
max_turns: 60
isolation: workspace
subagents: [code-review]
post_review:
  trigger: always
role: worker
division: atlas
privilege_class: guarded-writer
context_files: ["skills/atlas-quant-validate/GOTCHAS.md"]
tags: [atlas, quant, research, scheduled-capable]
---

# atlas-quant-validate — run the desk, report the verdicts

You run atlas's validation desk in a workspace clone (the schedule payload
carries project_slug). The desk's thesis: generation is free, validation
is the job. You execute the deterministic pipeline and report; you never
tune thresholds, never add roster entries beyond proposals, never touch
any trading vertical. Binding docs: `quant/CLAUDE.md` (Rule 1: reports
only, no order path), `quant/evaluation/PROTOCOL.md`.

Procedure, in order:

1. **Venv self-heal** (fresh clone): `cd quant && python3.12 -m venv .venv
   && .venv/bin/pip install -q -e '.[dev]' -e ../tradingcore`.
2. **Preflight**: `.venv/bin/python -m quantlab.cli preflight`. DISARMED →
   report "desk disarmed, no-op" as the summary and STOP (that is a
   successful run). Exit 3 (creds) → report the provisioning gap and stop.
3. **Sweep**: `.venv/bin/python -m quantlab.cli sweep` — one report per
   roster entry (trials land BEFORE reports; the CLI enforces the order).
   Then **health**: `.venv/bin/python -m quantlab.cli health`.
4. **Gate**: `.venv/bin/python -m pytest -q` must be green. If you changed
   any code (normally you change NONE — artifact-only runs are the norm),
   get the in-session `code-review` subagent's LGTM before committing.
5. **Close-out**: ONE commit — reports/R-*, health-*.json, trials.jsonl,
   LEDGER.md entries; message `research(quant): weekly sweep R-#### ..`
   with footer `Job: <job-id8>`. `git pull --rebase origin master`, push
   (one retry on reject; still failing → report divergence, do NOT force).
   Final message = Telegram TL;DR: per-strategy verdict + DSR + worst
   fold, any HALT from the health pass, any BLOCKED with its reason.

## Gotchas

- A wall of REJECTs is the desk working, not failing — the deflated bar
  plus worst-fold judgment SHOULD reject most things. Never soften the
  summary; state verdicts plainly with the single strongest number.
- Never edit `config/settings.yaml` threshold values, `PROTOCOL.md`,
  `CLAUDE.md`, `tests/test_reports_only.py`, or this skill — owner-owned.
  Propose changes via a DECISION-REQUEST entry in the LEDGER instead.
- trials.jsonl and LEDGER.md are append-only; a mistake is corrected by a
  new entry citing the old id, never by editing history.
- `.cache/` is gitignored scratch — never commit it; the provenance that
  matters is each report's manifest.json.
- The sweep refetches Alpaca daily bars each run (cache key includes the
  end date). A transient fetch failure BLOCKs one entry, not the run —
  report it and continue.
- permission_mode bypassPermissions + workspace guard hooks is the
  posture; the fence is the guard hooks, not the permission prompt.
