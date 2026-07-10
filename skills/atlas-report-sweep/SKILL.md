---
name: atlas-report-sweep
description: Weekly Atlas report sweep — enumerate the portfolio, every sector, and every holding, then produce the full report set (portfolio brief + sector reviews + per-asset reports)
model: claude-sonnet-4-6
effort: medium
permission_mode: bypassPermissions
required_tools: [Read, Bash, Glob, Grep]
max_turns: 100
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
tags: [atlas, finance, research, scheduled-capable]
---

# Atlas Report Sweep

The Sunday-evening full pass: one report per reportable target. Scheduled weekly; also
triggerable ad-hoc ("run the atlas report sweep").

## Procedure

From `$HOME/Library/Application Support/ai-server/projects/atlas`, after
`set -a; source .env; set +a`; CLI = `dashboard/.venv/bin/atlas-dash`.

### 1. Freshen data, then enumerate

```bash
atlas-dash refresh          # poll + indicators so every packet is current
atlas-dash report-targets   # {"portfolio": true, "sectors": [...], "holdings": [...]}
```

### 2. Fan out — one atlas-report job per target (preferred)

If the dispatch MCP tool (`enqueue_job`) is available in this session, enqueue one job per
target and finish:

- `atlas-report: portfolio brief`
- `atlas-report: sector <s>` for each sector
- `atlas-report: asset <symbol>` for each holding

Summary = the list of enqueued job ids per target. Each child session gets its own budget,
charter, and knowledge — failures stay isolated.

### 3. Fallback — sequential in this session

If enqueue is unavailable, produce the reports yourself IN THIS ORDER (sectors and portfolio
read per-asset `latest_suggestion`s, so assets go first): each holding → each sector →
portfolio brief. Follow the atlas-report skill's procedure per target (packet → charter +
knowledge → payload → save-report → learn on failure). If you approach your turn budget,
prioritize: portfolio brief > sectors > remaining assets, and list what was skipped.

### 4. Summary

Table: target → saved report id + evaluation score (or job id if fanned out, or SKIPPED).
Mention every `learn` entry filed. Reports render at https://atlas.chrispiserchia.com/reports.
