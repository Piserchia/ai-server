#!/usr/bin/env python
"""
scripts/cost-reconcile.py — the spec §2.8 calibration anchor from the JSONL
ledger at BOTH windows (trailing 30 d + 7 d), the per-kind step, the
computed-vs-SDK reconcile, the weekly-allowance calibration, the weekly
lane-budget seed, and (--db) the Phase-1 exit criterion "cost view reconciles
with JSONL sums at both windows and the 1-h rate": SUM(jobs.cost_usd_list) and
SUM(jobs.sdk_cost_usd) per model against the JSONL's two figures.

Run (project root, venv python):
    python scripts/cost-reconcile.py [--windows 30,7 | --days N] [--audit-dir P]
                                     [--db] [--json] [--seed-lane-budgets [PATH]]
    (from the dev checkout, settings.audit_log_dir is the PROD tree — the dev
     .env points SERVER_ROOT at production; pass --audit-dir to read elsewhere,
     and pass an explicit PATH to --seed-lane-budgets or omit the flag: the bare
     form writes under settings.server_root, i.e. production's volumes/)

Exit codes: 0 = a report; 1 = `credit_signature` (5-minute cache writes seen in
any window — the usage-credits signature, spec §2.8 — so the weekly timer's
non-zero exit is what gets it noticed); 2 = the audit dir does not exist;
3 = the run itself failed (the `--db` leg could not reach Postgres / the DSN is
wrong / the schema predates 008, or an unexpected error anywhere else — a
`... failed: <ExcType>: <msg>` line on stderr, the traceback in the log).
rc=1 is RESERVED for the credits signature: an infrastructure failure must
never be DM'd as "check claude.ai billing".

WIRED INTO LAUNCHD, weekly: scripts/cost-reconcile-run.sh (timer
`com.assistant.cost-reconcile`, Monday 07:30, D-P1-8 — a timer, not a schedule
row) runs `--windows 30,7 --db --seed-lane-budgets` and alerts on rc != 0.
The seed table is printed and written; `LANE_WEEKLY_BUDGET_JSON` stays a
hand-pasted Phase-3 setting.

Everything priced here comes from `src.runner.pricing` — the single definition
of `cost_usd_list`. Postgres is opened ONLY under --db (lazy import inside
`_db_rows`); the module import never touches it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings  # noqa: E402
from src.runner import pricing  # noqa: E402

DbRow = tuple[str, int, Decimal | None, Decimal | None]
DbRows = Callable[[datetime, datetime], Iterable[DbRow]]

# The DB leg groups by the SAME precedence the JSONL leg uses
# (`job_completed.model_served` first, the requested id second) so a family's
# two sums are keyed alike; BOTH cost columns (round-3 #10): cost_usd_list is
# the runner's computation, sdk_cost_usd the SDK's own figure. A Codex row has
# NULL in both and lands as a $0 "DB: n" line against the JSONL's unpriced
# block — counted, never priced.
DB_SQL = """
SELECT COALESCE(model_served, resolved_model, '') AS model,
       COUNT(*)                                     AS jobs,
       SUM(cost_usd_list)                           AS cost_usd_list,
       SUM(sdk_cost_usd)                            AS sdk_cost_usd
FROM jobs
WHERE status = 'completed'
  AND completed_at >= :since AND completed_at < :until
GROUP BY 1
ORDER BY 3 DESC NULLS LAST
"""


async def _db_rows_async(since: datetime, until: datetime) -> list[DbRow]:
    from sqlalchemy import text

    from src.db import async_session, engine

    # Review round 2 (major): `main` calls this once PER WINDOW, each under its
    # own `asyncio.run` loop, and `src.db.engine` is a module-level pooled
    # AsyncEngine. A pooled asyncpg connection is bound to the loop that
    # created it, so the second window's pre-ping would raise "attached to a
    # different loop" / "Event loop is closed" (not a DBAPI error — the pool
    # re-raises instead of recycling). SQLAlchemy's rule: dispose the engine
    # before reusing it under a new event loop. One fresh connection per
    # window is the right cost for a weekly script.
    try:
        async with async_session() as s:
            res = await s.execute(text(DB_SQL), {"since": since, "until": until})
            return [(m or "", int(n), usd, sdk) for m, n, usd, sdk in res.all()]
    finally:
        await engine.dispose()


def _db_rows(since: datetime, until: datetime) -> list[DbRow]:
    return asyncio.run(_db_rows_async(since, until))


def _windows(spec: str) -> list[int]:
    out = [int(x) for x in str(spec).replace(" ", "").split(",") if x]
    return out or [30, 7]


def load_ledger(audit_dir: Path) -> tuple[list[pricing.JobCost], list[pricing.QuotaReading]]:
    """Every per-job trace under the audit dir → (priced jobs, seven_day
    readings). INDEX.jsonl is the audit index, not a job trace; sub-directories
    (D1's `schedules/` stream) are not job traces either."""
    jobs: list[pricing.JobCost] = []
    readings: list[pricing.QuotaReading] = []
    for f in sorted(audit_dir.glob("*.jsonl")):
        if f.name == "INDEX.jsonl":
            continue
        events = pricing.read_events(f)
        readings.extend(pricing.quota_readings(events))
        jc = pricing.job_cost_from_events(f.stem, events)
        if jc is not None:
            jobs.append(jc)
    return jobs, readings


def _db_rows_dict(rows: Iterable[DbRow]) -> list[dict[str, Any]]:
    return [{"model": m, "jobs": n,
             "cost_usd_list": str(usd) if usd is not None else None,
             "sdk_cost_usd": str(sdk) if sdk is not None else None}
            for m, n, usd, sdk in rows]


def main(argv: list[str] | None = None, *, db_rows: DbRows = _db_rows) -> int:
    p = argparse.ArgumentParser(
        description="Two-window list-price ledger from the JSONL audit log (spec §2.8).")
    # Spec §9 P0: BOTH windows in one invocation. --days N is kept as an alias.
    p.add_argument("--windows", default="30,7",
                   help="comma list of trailing-day windows (default 30,7)")
    p.add_argument("--days", type=int, default=None, help="alias for --windows N")
    p.add_argument("--audit-dir", default=None,
                   help="default settings.audit_log_dir (the PROD tree from the dev checkout)")
    p.add_argument("--db", action="store_true",
                   help="also reconcile SUM(jobs.cost_usd_list) / SUM(jobs.sdk_cost_usd) per model")
    p.add_argument("--json", action="store_true", help="one JSON document instead of the tables")
    p.add_argument("--seed-lane-budgets", nargs="?", const="", default=None, metavar="PATH",
                   help="write the trailing-7-d × 1.2 per-lane seed (spec §2.5/§2.8); "
                        "default PATH volumes/telemetry/lane_budget_seed.json")
    args = p.parse_args(argv)
    windows = [args.days] if args.days else _windows(args.windows)
    audit_dir = Path(args.audit_dir) if args.audit_dir else settings.audit_log_dir
    if not audit_dir.is_dir():
        print(f"no such audit dir: {audit_dir}", file=sys.stderr)
        return 2
    until = datetime.now(timezone.utc)
    jobs, readings = load_ledger(audit_dir)
    reports = pricing.summarize_windows(jobs, until=until, windows=windows)
    # The weekly denominator, re-derived from the seven_day series rather than
    # carried as a constant (spec §9 P0 row, §2.8; round-3 #6). It is a property
    # of the quota window, not of a report window: computed once over all jobs.
    allowance = pricing.weekly_allowance(jobs, readings)
    doc: dict[str, Any] = {
        "audit_dir": str(audit_dir), "until": until.isoformat(),
        "windows": [r.to_dict() for r in reports],
        "weekly_allowance": allowance.to_dict() if allowance is not None else None,
        "credit_signature": any(r.credit_signature for r in reports),
        "prices_as_of": pricing.PRICES_AS_OF,
    }
    text_out: list[str] = []
    if not args.json:
        for rep in reports:
            text_out.append(pricing.render_table(rep))
            text_out.append("")
            # The Phase-1 exit criterion, printed every run (round-3 #10): ours
            # vs the SDK's, with the implied cache-write rate when they diverge.
            text_out.append(pricing.render_sdk_reconcile(rep))
            text_out.append("")
        text_out.append(pricing.render_weekly_allowance(allowance))
        text_out.append("")
    if args.db:
        doc["db"] = []
        for rep in reports:
            # Review round 1: a DB outage is rc=3, never rc=1 — the wrapper
            # reads 1 as the credits signature. asyncpg / SQLAlchemy errors
            # carry no DSN or password, so the message is safe for the log.
            try:
                rows = list(db_rows(rep.since, rep.until))
            except Exception as exc:  # noqa: BLE001 — any failure is "the run failed"
                print(f"DB leg failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                return 3
            table = pricing.render_db_delta(rep, rows)
            doc["db"].append({"days": rep.days, "rows": _db_rows_dict(rows), "table": table})
            if not args.json:
                text_out.append(f"-- DB reconcile, trailing {rep.days} d --")
                text_out.append(table)
                text_out.append("")
    if args.seed_lane_budgets is not None:
        # The seed is ALWAYS the shortest window (spec §2.8: trailing-7-d × 1.2,
        # never the 30-d mean, which predates the alpha flywheel).
        seed_rep = min(reports, key=lambda r: r.days)
        out = (Path(args.seed_lane_budgets) if args.seed_lane_budgets
               else settings.server_root / "volumes" / "telemetry" / "lane_budget_seed.json")
        pricing.write_lane_seed(seed_rep, out)
        seed = pricing.lane_seed(seed_rep)
        doc["lane_seed"] = {"path": str(out), "window_days": seed_rep.days,
                            "multiplier": "1.2", "approximated_lanes": True,
                            "weekly_budget_usd": seed}
        if not args.json:
            text_out.append(f"lane budget seed (trailing {seed_rep.days} d × 1.2) → {out}")
            text_out.append("-- paste into LANE_WEEKLY_BUDGET_JSON (Phase 3; approximated lanes, "
                            "jobs.lane is NULL until then) --")
            for lane, usd in seed.items():
                text_out.append(f"  {lane:<28} {usd:>10}")
            text_out.append("")
    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print("\n".join(text_out).rstrip())
    # A 5-minute cache write is the usage-credits signature (§2.8): non-zero exit
    # so the weekly timer's failure is what surfaces it.
    return 1 if doc["credit_signature"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — a ledger-parse crash is never rc=1 either
        print(f"cost-reconcile failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)
