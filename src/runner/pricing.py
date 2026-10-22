"""
List-price ledger for Claude usage (Phase 1 B1; spec §2.8, §9 "1 — Observability").

`cost_usd_list` is a LIST-PRICE EQUIVALENT — never a bill (the fleet runs on
the Max subscription). This module is its SINGLE DEFINITION: the runner calls
`price_usage` when it stamps `jobs.cost_usd_list` (B3), the SDK's own
`total_cost_usd` is stored separately as `jobs.sdk_cost_usd`, and
`scripts/cost-reconcile.py` (B4) is what compares them.

Consumers:
  * runner.session (B3) — `price_usage(model_served or model, usage)` on the
    Anthropic lane; `None` on the Codex lane (no Codex price table in Phase 1).
  * runner.result_capture (B2) — `cache_write_buckets` for `usage_columns`.
  * scripts/cost-reconcile.py (B4) — the §2.8 calibration table from the JSONL
    ledger at BOTH windows (30 d + 7 d), the per-kind step, the computed-vs-SDK
    reconcile, the weekly-allowance calibration and the lane-budget seed.

Prices: docs/research/llm-landscape-2026-09/claude-anthropic.md §4 (fetched
2026-09-24). EACH cache-write bucket is priced at ITS OWN rate — 1-h writes at
cache_write_1h, 5-m writes at cache_write_5m, read from
usage.cache_creation.ephemeral_{1h,5m}_input_tokens (spec §2.3 row 007, §2.8).
There is no global TTL setting: the subscription's TTL is 1 h and prod records
100 % of writes there, so a single 5-m rate made round 1's anchor ≈ 19 % low,
and a non-zero 5-m reading is itself the usage-credits signature (§2.8).

Model identity (re-cut deltas): a job is priced by `job_completed.model_served`
first, `job_started.model` second; a non-Anthropic provider (`job_started` /
`job_completed.provider`) is NEVER priced as a Claude family — it is counted
under `unpriced` with the provider named. `_ts` accepts epoch (prod's
`rate_limit_status.resets_at` is an epoch integer) and ISO stamps.

Pure module: no I/O beyond read_events() and write_lane_seed().
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PRICES_AS_OF = "2026-09-24"
_M = Decimal(1_000_000)
_CENTS = Decimal("0.01")


def usd_2dp(value: Decimal) -> Decimal:
    """Dollars to the cent the way the spec's figures are rounded (half UP:
    $3.485 → $3.49, the §2.8 / DoneCard figure). Python's Decimal default is
    half-EVEN (3.485 → 3.48), so every `$` cell the renderers print goes
    through here rather than through `round()` / `:.2f`."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)

# Providers whose model ids are Claude families; anything else is unpriced.
ANTHROPIC_PROVIDERS = frozenset({"anthropic"})


@dataclass(frozen=True)
class Price:
    input: Decimal
    cache_write_5m: Decimal
    cache_write_1h: Decimal
    cache_read: Decimal
    output: Decimal


def _p(i, w5, w1, r, o) -> Price:
    return Price(Decimal(str(i)), Decimal(str(w5)), Decimal(str(w1)), Decimal(str(r)), Decimal(str(o)))


# claude-anthropic.md §4 "API list prices ($/MTok)"; family prefix → price.
LIST_PRICES: dict[str, Price] = {
    "claude-fable-5-1": _p(10, 12.50, 20, 0.25, 50),
    "claude-fable-5":   _p(10, 12.50, 20, 1.00, 50),
    "claude-opus-5-5":  _p(4, 5, 8, 0.20, 20),
    "claude-opus-5":    _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-8":  _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-7":  _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-6":  _p(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-5":  _p(5, 6.25, 10, 0.50, 25),
    "claude-sonnet-5":  _p(2, 2.50, 4, 0.20, 10),
    "claude-sonnet-4-6": _p(3, 3.75, 6, 0.30, 15),
    "claude-sonnet-4-5": _p(3, 3.75, 6, 0.30, 15),
    "claude-haiku-4-5": _p(1, 1.25, 2, 0.10, 5),
}

# Phase-1 lane approximation (jobs.lane is NULL until Phase 3 fills it). Only
# used to shape the weekly budget seed, and labelled "approximated" in its
# output. `pwa`/`cli` never appear in Phase-1 data; the P0 4-set is kept.
_ATLAS_PREFIXES = ("atlas-", "alpha-", "momentum-", "swing-", "firm-")
_KERNEL_SKILLS = frozenset({"server-patch", "server-deploy", "deploy-director",
                            "review-and-improve", "self-diagnose"})
_OWNER_CHANNELS = frozenset({"telegram", "web", "pwa", "cli"})


def lane_for(skill: str | None, job_kind: str | None, origin_channel: str | None) -> str:
    """The §2.5 lane a job would land in — the Phase-1 APPROXIMATION
    (jobs.lane is NULL until Phase 3; the weekly budgets live in Settings as
    LANE_WEEKLY_BUDGET_JSON)."""
    s = (skill or "").strip().lower()
    k = (job_kind or "").strip().lower()
    if (origin_channel or "").strip().lower() in _OWNER_CHANNELS:
        return "owner"
    if any(s.startswith(p) for p in _ATLAS_PREFIXES):
        return "atlas"
    if s in _KERNEL_SKILLS:
        return "kernel"
    if k.startswith("_") or s.startswith("_") or k == "chat":
        return "utility"
    return "background"


def _tok(usage: dict[str, Any] | None, key: str) -> int:
    try:
        return int((usage or {}).get(key) or 0)
    except (TypeError, ValueError):
        return 0


def cache_write_buckets(usage: dict[str, Any] | None) -> tuple[int, int]:
    """(1-hour, 5-minute) cache-write tokens. The nested cache_creation object
    is authoritative; when it is absent the flat cache_creation_input_tokens is
    attributed to the 1-HOUR arm (spec §2.8: prod records 100 % as 1-h, and the
    flat key equals the 1-h figure on every row checked). A Codex-mapped usage
    (flat key only) therefore lands on the 1-h arm too — B2's `usage_columns`
    reuses this so the two lanes cannot drift."""
    nested = (usage or {}).get("cache_creation")
    if isinstance(nested, dict) and (
            "ephemeral_1h_input_tokens" in nested or "ephemeral_5m_input_tokens" in nested):
        return (_tok(nested, "ephemeral_1h_input_tokens"),
                _tok(nested, "ephemeral_5m_input_tokens"))
    return _tok(usage, "cache_creation_input_tokens"), 0


def family_for(model: str | None) -> str | None:
    """Longest family prefix with a boundary (end or '-') after it; None for
    bare aliases (`sonnet`), unknown ids and provider-qualified ids."""
    m = (model or "").strip().lower()
    best: str | None = None
    for fam in LIST_PRICES:
        if m == fam or m.startswith(fam + "-"):
            if best is None or len(fam) > len(best):
                best = fam
    return best


def price_usage(model: str | None, usage: dict[str, Any] | None) -> Decimal | None:
    """List-price equivalent for one job's usage — THE definition of
    `cost_usd_list`. Each cache-write bucket at its own rate (spec §2.3 row
    007, §2.8); None for a bare alias / unknown id / non-Anthropic id so the
    caller can COUNT it under `unpriced` instead of mispricing it. A known
    family with no tokens is Decimal(0), not None. `usage` is the session
    TOTAL: a session whose subagents ran on another family is priced at
    `model`'s rate for the whole total (the B4 reconcile shows it as drift)."""
    fam = family_for(model)
    if fam is None:
        return None
    p = LIST_PRICES[fam]
    w1h, w5m = cache_write_buckets(usage)
    total = (Decimal(_tok(usage, "input_tokens")) * p.input
             + Decimal(_tok(usage, "output_tokens")) * p.output
             + Decimal(_tok(usage, "cache_read_input_tokens")) * p.cache_read
             + Decimal(w1h) * p.cache_write_1h
             + Decimal(w5m) * p.cache_write_5m) / _M
    return total.normalize() if total else Decimal(0)


@dataclass(frozen=True)
class JobCost:
    job_id: str
    model: str                   # job_completed.model_served, else job_started.model
    requested_model: str         # job_started.model (the record; never priced when served is known)
    provider: str | None         # job_started.provider / job_completed.provider (absent pre-slice)
    family: str | None           # None ⇒ unpriced (alias / unknown / non-Anthropic provider)
    skill: str                   # job_started.skill or .job_kind — the §2.8 row label
    lane: str                    # lane_for(...) — Phase-1 approximation, seed only
    completed_at: datetime | None
    input: int
    cache_read: int
    cache_write_1h: int
    cache_write_5m: int
    output: int
    usd_sdk: Decimal | None      # job_completed.sdk_cost_usd (B3+) — the SDK's own
                                 # total_cost_usd. `usd` below is OURS, from tokens.

    @property
    def usage(self) -> dict[str, Any]:
        return {"input_tokens": self.input, "output_tokens": self.output,
                "cache_read_input_tokens": self.cache_read,
                "cache_creation_input_tokens": self.cache_write_1h + self.cache_write_5m,
                "cache_creation": {"ephemeral_1h_input_tokens": self.cache_write_1h,
                                   "ephemeral_5m_input_tokens": self.cache_write_5m}}

    @property
    def tokens(self) -> int:
        return (self.input + self.cache_read + self.cache_write_1h
                + self.cache_write_5m + self.output)

    @property
    def usd(self) -> Decimal | None:
        if self.family is None:
            return None
        return price_usage(self.model, self.usage)

    @property
    def unpriced_label(self) -> str:
        """The row label under `unpriced`: the provider is named for a
        non-Anthropic job (`codex/gpt-5-codex`), never doubled when the id is
        already qualified."""
        model = self.model or "(empty)"
        if self.provider and self.provider not in ANTHROPIC_PROVIDERS:
            prefix = f"{self.provider}/"
            return model if model.startswith(prefix) else prefix + model
        return model


def read_events(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        if isinstance(evt, dict):
            out.append(evt)
    return out


def _ts(value: Any) -> datetime | None:
    """Parse an audit timestamp: ISO 8601 (audit `ts`, `Z` accepted, a naive
    stamp read as UTC) OR an epoch in seconds (prod's `resets_at` is an epoch
    integer; a numeric string counts too). None for anything else."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromtimestamp(float(text), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _provider_of(started: dict[str, Any], done: dict[str, Any]) -> str | None:
    for evt in (done, started):
        p = evt.get("provider")
        if p:
            return str(p).strip().lower()
    return None


def job_cost_from_events(job_id: str, events: Iterable[dict[str, Any]]) -> JobCost | None:
    started = done = None
    for evt in events:
        kind = evt.get("kind")
        if kind == "job_started" and started is None:
            started = evt
        elif kind == "job_completed":
            done = evt                      # last terminal wins (reconcile.py semantics)
    if started is None or done is None:
        return None
    requested = str(started.get("model") or "")
    served = done.get("model_served")
    model = str(served).strip() if served else requested
    provider = _provider_of(started, done)
    # A non-Anthropic provider is never priced as a Claude family, whatever the
    # served id looks like (Review Focus 7); an absent provider is a pre-slice
    # Anthropic row.
    family = family_for(model) if provider is None or provider in ANTHROPIC_PROVIDERS else None
    usage = done.get("usage") if isinstance(done.get("usage"), dict) else {}
    # The SDK's figure lives in its own field from B3 on; cost_usd_list in the
    # same event is the runner's computation of `usd`, so reading it here
    # would compare this module to itself (round-3 #10).
    sdk = done.get("sdk_cost_usd")
    skill = str(started.get("skill") or started.get("job_kind") or "(none)")
    w1h, w5m = cache_write_buckets(usage)
    try:
        usd_sdk = Decimal(str(sdk)) if sdk is not None else None
    except InvalidOperation:
        usd_sdk = None
    return JobCost(
        job_id=job_id, model=model, requested_model=requested, provider=provider,
        family=family, skill=skill,
        lane=lane_for(started.get("skill"), started.get("job_kind"),
                      started.get("origin_channel")),
        completed_at=_ts(done.get("ts")),
        input=_tok(usage, "input_tokens"), cache_read=_tok(usage, "cache_read_input_tokens"),
        cache_write_1h=w1h, cache_write_5m=w5m, output=_tok(usage, "output_tokens"),
        usd_sdk=usd_sdk,
    )


@dataclass
class ModelRow:
    model: str
    jobs: int = 0
    input: int = 0
    cache_read: int = 0
    cache_write_1h: int = 0
    cache_write_5m: int = 0
    output: int = 0
    usd: Decimal = Decimal(0)        # each bucket at its own rate (spec §2.8)
    usd_sdk: Decimal | None = None
    sdk_jobs: int = 0

    def add(self, jc: JobCost) -> None:
        self.jobs += 1
        self.input += jc.input
        self.cache_read += jc.cache_read
        self.cache_write_1h += jc.cache_write_1h
        self.cache_write_5m += jc.cache_write_5m
        self.output += jc.output
        self.usd += jc.usd or Decimal(0)
        if jc.usd_sdk is not None:
            self.usd_sdk = (self.usd_sdk or Decimal(0)) + jc.usd_sdk
            self.sdk_jobs += 1

    @property
    def tokens(self) -> int:
        return (self.input + self.cache_read + self.cache_write_1h
                + self.cache_write_5m + self.output)


@dataclass
class KindRow:
    """The §2.8 "where the tokens go" step, per skill — the view that makes the
    alpha-flywheel line item visible instead of averaged away."""
    kind: str
    jobs: int = 0
    tokens: int = 0
    usd: Decimal = Decimal(0)

    def add(self, jc: JobCost) -> None:
        self.jobs += 1
        self.tokens += jc.tokens
        self.usd += jc.usd or Decimal(0)


def _row_dict(r: Any) -> dict[str, Any]:
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.__dict__.items()}


@dataclass
class LedgerReport:
    since: datetime
    until: datetime
    days: int
    per_model: list[ModelRow] = field(default_factory=list)
    per_kind: list[KindRow] = field(default_factory=list)
    unpriced: list[ModelRow] = field(default_factory=list)
    per_lane: dict[str, Decimal] = field(default_factory=dict)
    totals: ModelRow = field(default_factory=lambda: ModelRow("total"))
    median_job: dict[str, int] = field(default_factory=dict)
    median_usd_by_family: dict[str, Decimal] = field(default_factory=dict)

    @property
    def credit_signature(self) -> bool:
        """A 5-m cache write on this account means the TTL dropped to 5 m, which
        is the usage-credits signature (spec §2.8 metered-spend tripwires)."""
        return self.totals.cache_write_5m > 0

    def to_dict(self) -> dict[str, Any]:
        return {"since": self.since.isoformat(), "until": self.until.isoformat(),
                "days": self.days,
                "per_model": [_row_dict(r) for r in self.per_model],
                "per_kind": [_row_dict(r) for r in self.per_kind],
                "unpriced": [_row_dict(r) for r in self.unpriced],
                "per_lane": {k: str(v) for k, v in self.per_lane.items()},
                "totals": _row_dict(self.totals), "median_job": self.median_job,
                "median_usd_by_family": {k: str(v) for k, v in self.median_usd_by_family.items()},
                "credit_signature": self.credit_signature, "prices_as_of": PRICES_AS_OF}


def summarize(jobs: Iterable[JobCost], *, since: datetime, until: datetime,
              days: int) -> LedgerReport:
    rep = LedgerReport(since=since, until=until, days=days)
    rows: dict[str, ModelRow] = {}
    kinds: dict[str, KindRow] = {}
    unpriced: dict[str, ModelRow] = {}
    lanes: dict[str, Decimal] = {}
    kept: list[JobCost] = []
    by_family: dict[str, list[Decimal]] = {}
    for jc in jobs:
        if jc.completed_at is None or not (since <= jc.completed_at < until):
            continue
        kept.append(jc)
        if jc.family is not None:
            rows.setdefault(jc.family, ModelRow(jc.family)).add(jc)
            by_family.setdefault(jc.family, []).append(jc.usd or Decimal(0))
        else:
            label = jc.unpriced_label
            unpriced.setdefault(label, ModelRow(label)).add(jc)
        kinds.setdefault(jc.skill, KindRow(jc.skill)).add(jc)
        lanes[jc.lane] = lanes.get(jc.lane, Decimal(0)) + (jc.usd or Decimal(0))
        rep.totals.add(jc)
    rep.per_model = sorted(rows.values(), key=lambda r: -r.usd)
    rep.per_kind = sorted(kinds.values(), key=lambda r: -r.tokens)
    rep.unpriced = sorted(unpriced.values(), key=lambda r: -r.jobs)
    rep.per_lane = dict(sorted(lanes.items(), key=lambda kv: -kv[1]))
    if kept:
        rep.median_job = {k: int(statistics.median(getattr(j, k) for j in kept))
                          for k in ("cache_read", "cache_write_1h", "cache_write_5m",
                                    "output", "input")}
        rep.median_usd_by_family = {fam: statistics.median(vals)
                                    for fam, vals in sorted(by_family.items())}
    return rep


def summarize_windows(jobs: Iterable[JobCost], *, until: datetime,
                      windows: Sequence[int] = (30, 7)) -> list[LedgerReport]:
    """One report per window, in the order given. Spec §9 requires BOTH the
    trailing 30 d and the trailing 7 d in one invocation, because the load's
    largest step (the alpha flywheel, 2026-09-23) post-dates the 30-d mean."""
    kept = list(jobs)
    return [summarize(kept, since=until - timedelta(days=d), until=until, days=d)
            for d in windows]


def lane_seed(rep: LedgerReport, *,
              multiplier: Decimal = Decimal("1.2")) -> dict[str, str]:
    """Per-lane weekly budget seed = this report's per-lane cost × 1.2 (spec
    §2.5 `lanes.<lane>.weekly_budget`, §2.8, round-2 #18: re-seeded WEEKLY from
    the trailing 7 d, never from the 30-d mean). Lanes are the Phase-1
    approximation of lane_for(); Phase 3 recomputes them from jobs.lane. The
    seed's only consumer is LANE_WEEKLY_BUDGET_JSON in Settings (hand-pasted
    at Phase 3, D-P1-8); routing-policy.yml is deferred."""
    return {lane: str((usd * multiplier).quantize(Decimal("0.01")))
            for lane, usd in rep.per_lane.items()}


def write_lane_seed(rep: LedgerReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "as_of": rep.until.isoformat(), "window_days": rep.days,
        "multiplier": "1.2", "approximated_lanes": True,
        "weekly_budget_usd": lane_seed(rep),
    }, indent=2) + "\n", encoding="utf-8")
    return path


# ── The computed-vs-SDK reconcile (Phase-1 exit criterion, round-3 #10) ─────


def implied_cache_write_rate(row: ModelRow) -> Decimal | None:
    """The $/MTok cache-write rate that would make the SDK's total equal ours.

    Price the other three legs at list, subtract, divide by the cache-write
    tokens. This is what turns "the two disagree by 19 %" into "the CLI prices
    cache writes at ≈ $6.25/M, i.e. the 5-minute rate" — which is the form the
    exit criterion asks for ("the divergence is recorded together with the
    rate the CLI uses"). None when there is nothing to solve for.
    """
    price = LIST_PRICES.get(row.model)
    writes = row.cache_write_1h + row.cache_write_5m
    if price is None or row.usd_sdk is None or writes <= 0:
        return None
    others = (Decimal(row.input) * price.input
              + Decimal(row.cache_read) * price.cache_read
              + Decimal(row.output) * price.output) / _M
    return ((row.usd_sdk - others) * _M / Decimal(writes)).quantize(Decimal("0.01"))


def render_sdk_reconcile(rep: LedgerReport) -> str:
    """Per model: our computation vs the SDK's, the delta, and the implied rate.

    The exit criterion is "cost_usd_list (runner-computed, 1-h rate) and
    jobs.sdk_cost_usd agree within 1 %, or the divergence is recorded with the
    rate the CLI uses" (spec §9, §2.8). Before round 3 both columns came from
    the SDK, so this table would have shown 0.0 % forever.
    """
    lines = ["-- computed vs SDK (exit criterion: within 1 %, else record the rate) --",
             f"{'model':<20} {'computed $':>11} {'SDK $':>11} {'delta':>8} {'implied cw $/M':>15}"]
    flagged = False
    for r in rep.per_model:
        if r.usd_sdk is None or not r.usd:
            lines.append(f"{r.model:<20} {usd_2dp(r.usd):>11.2f} {'—':>11} {'':>8} {'':>15}")
            continue
        delta = (r.usd_sdk - r.usd) / r.usd * 100
        rate = implied_cache_write_rate(r)
        mark = "" if abs(delta) <= 1 else "  ⚠"
        flagged = flagged or bool(mark)
        lines.append(f"{r.model:<20} {usd_2dp(r.usd):>11.2f} {usd_2dp(r.usd_sdk):>11.2f} {delta:>7.1f}%"
                     f" {(f'{rate:.2f}' if rate is not None else '—'):>15}{mark}")
    if flagged:
        lines.append("⚠ >1 % divergence: record the implied cache-write rate in the Phase-1 PR. "
                     "$10.00/M is the 1-h Opus rate this plan prices at, $6.25/M the 5-m rate "
                     "(a whole-ledger ≈ −19 % is exactly that substitution; spec §2.8).")
    return "\n".join(lines)


# ── Weekly-allowance calibration from the seven_day series (spec §9) ────────


@dataclass(frozen=True)
class QuotaReading:
    ts: datetime
    utilization: Decimal
    resets_at: datetime | None


def quota_readings(events: Iterable[dict[str, Any]]) -> list[QuotaReading]:
    """Every `rate_limit_status` event carrying a seven_day utilization.

    session.py already audits `rate_limit_status{status, utilization, resets_at,
    rate_limit_type}` on every RateLimitEvent, so this is a read of data the
    fleet has been collecting — no new instrumentation. `five_hour` readings
    are not the weekly bar and are skipped. `resets_at` is an epoch integer on
    prod; `_ts` reads both forms.
    """
    out: list[QuotaReading] = []
    for evt in events:
        if evt.get("kind") != "rate_limit_status":
            continue
        if str(evt.get("rate_limit_type") or "") != "seven_day":
            continue
        util = evt.get("utilization")
        ts = _ts(evt.get("ts"))
        if util is None or ts is None:
            continue
        try:
            u = Decimal(str(util))
        except (ArithmeticError, ValueError):
            continue
        if not u.is_finite() or u <= 0:
            continue
        out.append(QuotaReading(ts=ts, utilization=u, resets_at=_ts(evt.get("resets_at"))))
    return sorted(out, key=lambda r: r.ts)


@dataclass(frozen=True)
class WeeklyCalibration:
    window_opens_at: datetime | None
    points: tuple[tuple[datetime, Decimal, Decimal], ...]   # (ts, utilization, usd since open)
    implied_usd: tuple[Decimal, ...]
    marginal_usd: Decimal | None
    working: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_opens_at": self.window_opens_at.isoformat() if self.window_opens_at else None,
            "points": [{"ts": ts.isoformat(), "utilization": str(u), "usd_since_open": str(s)}
                       for ts, u, s in self.points],
            "implied_usd": [str(v) for v in self.implied_usd],
            "marginal_usd": str(self.marginal_usd) if self.marginal_usd is not None else None,
            "working_usd": str(self.working),
        }


def weekly_allowance(jobs: Iterable[JobCost], readings: Iterable[QuotaReading], *,
                     working: Decimal = Decimal("200")) -> WeeklyCalibration | None:
    """Calibrate the weekly window IN DOLLARS, which is the unit the budgets use.

    spec §2.8: the window is FIXED, not rolling (every seven_day reading shares
    one resets_at), so "spent since the window opened" is well-defined:
    window_opens_at = resets_at − 7 d. For each reading, the allowance implied
    by that point is (spend since open) / utilization; the marginal figure is
    Δspend / Δutilization between the first and last reading, which is the one
    that ignores whatever was spent before the series started. None when no
    seven_day reading carries a resets_at — stated, never assumed.
    """
    reads = sorted((r for r in readings if r.resets_at is not None), key=lambda r: r.ts)
    if not reads:
        return None
    opens = max(r.resets_at for r in reads) - timedelta(days=7)
    priced = sorted((j for j in jobs
                     if j.completed_at is not None and j.completed_at >= opens
                     and j.usd is not None),
                    key=lambda j: j.completed_at)
    points: list[tuple[datetime, Decimal, Decimal]] = []
    for r in reads:
        spend = sum((j.usd for j in priced if j.completed_at <= r.ts), Decimal(0))
        points.append((r.ts, r.utilization, spend))
    implied = tuple((spend / util).quantize(Decimal("1"))
                    for _, util, spend in points if util > 0)
    marginal: Decimal | None = None
    if len(points) >= 2:
        du = points[-1][1] - points[0][1]
        ds = points[-1][2] - points[0][2]
        if du > 0:
            marginal = (ds / du).quantize(Decimal("1"))
    return WeeklyCalibration(window_opens_at=opens, points=tuple(points),
                             implied_usd=implied, marginal_usd=marginal, working=working)


def render_weekly_allowance(cal: WeeklyCalibration | None) -> str:
    if cal is None or not cal.points:
        return ("-- weekly allowance -- no seven_day utilization readings in this window; "
                "the $200/week working denominator stands unre-derived (spec §2.8)")
    lines = [f"-- weekly allowance (fixed window opened {cal.window_opens_at:%Y-%m-%d %H:%MZ}; "
             f"spec §2.8) --"]
    for ts, util, spend in cal.points:
        lines.append(f"  {ts:%m-%d %H:%MZ}  utilization {util:>5}  "
                     f"spent ${spend:>8.2f}  ⇒ allowance ≈ ${spend / util:>8.0f}/week")
    if cal.implied_usd:
        lines.append(f"  bracket ≈ ${min(cal.implied_usd)}–{max(cal.implied_usd)}/week"
                     + (f"; marginal ≈ ${cal.marginal_usd}/week" if cal.marginal_usd else ""))
    lines.append(f"  working denominator ${cal.working}/week (spec §2.8) — RE-DERIVE IT FROM "
                 f"THIS BLOCK weekly; it is never a constant in code")
    return "\n".join(lines)


# ── Rendering ───────────────────────────────────────────────────────────────


def _fmt_m(n: int) -> str:
    return f"{n / 1_000_000:8.1f}M"


def render_table(rep: LedgerReport) -> str:
    lines = [f"== trailing {rep.days} d == {rep.since:%Y-%m-%d} → {rep.until:%Y-%m-%d} "
             f"(prices as of {PRICES_AS_OF}; list-equivalent, never a bill; "
             f"each cache-write bucket at its own rate)",
             f"{'model':<20} {'jobs':>5} {'cache_read':>10} {'cw_1h':>9} {'cw_5m':>9} {'output':>9} {'$ list':>10} {'$ SDK (n)':>14}"]
    for r in rep.per_model + [rep.totals]:
        sdk = f"{usd_2dp(r.usd_sdk):.2f} ({r.sdk_jobs})" if r.usd_sdk is not None else "—"
        lines.append(f"{r.model:<20} {r.jobs:>5} {_fmt_m(r.cache_read):>10} {_fmt_m(r.cache_write_1h):>9} {_fmt_m(r.cache_write_5m):>9} {_fmt_m(r.output):>9} {usd_2dp(r.usd):>10.2f} {sdk:>14}")
    if rep.unpriced:
        lines.append("unpriced (bare alias / unknown id / non-Anthropic provider — "
                     "counted, never priced):")
        for r in rep.unpriced:
            lines.append(f"  {r.model:<18} {r.jobs:>5} {_fmt_m(r.cache_read):>10} {_fmt_m(r.cache_write_1h):>9} {_fmt_m(r.cache_write_5m):>9} {_fmt_m(r.output):>9}")
    if rep.per_kind:
        # The §2.8 step: three skills are ≈ 38 % of the window and one of them
        # (alpha-research) tripled the load on 2026-09-23. A per-model table
        # alone hides that.
        lines.append(f"-- by kind (the §2.8 step) --   {'jobs':>5} {'tokens':>10} {'$ list':>10}")
        for k in rep.per_kind[:15]:
            share = (k.tokens / rep.totals.tokens * 100) if rep.totals.tokens else 0.0
            lines.append(f"  {k.kind:<28} {k.jobs:>5} {_fmt_m(k.tokens):>10} {usd_2dp(k.usd):>10.2f}  ({share:4.1f} %)")
    if rep.per_lane:
        lines.append("-- by lane (approximated §2.5 lanes; jobs.lane is NULL until Phase 3) --")
        for lane, usd in rep.per_lane.items():
            lines.append(f"  {lane:<28} {usd_2dp(usd):>10.2f}")
    if rep.median_job:
        m = rep.median_job
        lines.append(f"median job: {m['cache_read'] / 1000:.0f}k cache-read / "
                     f"{m['cache_write_1h'] / 1000:.0f}k 1-h write / "
                     f"{m['cache_write_5m'] / 1000:.0f}k 5-m write / {m['output'] / 1000:.1f}k output")
    if rep.median_usd_by_family:
        meds = "  ".join(f"{fam.replace('claude-', '')} ${usd_2dp(v):.2f}"
                         for fam, v in rep.median_usd_by_family.items())
        lines.append(f"median $ per job by family: {meds}")
    if rep.credit_signature:
        lines.append("⚠ 5-minute cache writes present — possible usage-credit overflow "
                     "(spec §2.8 metered-spend tripwires): the TTL drop to 5 m is the "
                     "credits signature. Check claude.ai billing before anything else.")
    return "\n".join(lines)


def render_db_delta(rep: LedgerReport,
                    rows: Iterable[tuple[str, int, Decimal | None, Decimal | None]]) -> str:
    """The DB leg, per model, for BOTH cost columns (round-3 #10).

    `SUM(jobs.cost_usd_list)` vs the JSONL's computed figure is a
    same-computation-twice consistency check (did every completed job write the
    column *and* the event?), and `SUM(jobs.sdk_cost_usd)` vs the JSONL's SDK
    figure is the same check for the vendor's number. The interesting comparison
    — ours vs the SDK's — is render_sdk_reconcile(); keeping them apart is what
    stops "the reconcile" from meaning two different things again.
    """
    jsonl = {r.model: r for r in rep.per_model}
    seen: set[str] = set()
    lines = [f"{'model':<20} {'DB jobs':>7} {'DB computed':>12} {'JSONL computed':>14} "
             f"{'delta':>7} {'DB SDK':>10} {'JSONL SDK':>10} {'delta':>7}"]
    for model, n, usd, usd_sdk in rows:
        fam = family_for(model or "") or (model or "(empty)")
        seen.add(fam)
        db_c, db_s = Decimal(str(usd or 0)), Decimal(str(usd_sdk or 0))
        j = jsonl.get(fam)
        if j is None:
            lines.append(f"{fam:<20} {n:>7} {usd_2dp(db_c):>12.2f} {'JSONL: none':>14} {'':>7} "
                         f"{usd_2dp(db_s):>10.2f} {'':>10} {'':>7}")
            continue
        d_c = (db_c - j.usd) / j.usd * 100 if j.usd else Decimal(0)
        d_s = ((db_s - j.usd_sdk) / j.usd_sdk * 100
               if j.usd_sdk else Decimal(0))
        j_sdk = f"{usd_2dp(j.usd_sdk):.2f}" if j.usd_sdk is not None else "—"
        lines.append(f"{fam:<20} {n:>7} {usd_2dp(db_c):>12.2f} {usd_2dp(j.usd):>14.2f} {d_c:>6.1f}% "
                     f"{usd_2dp(db_s):>10.2f} {j_sdk:>10} {d_s:>6.1f}%")
    for fam, j in jsonl.items():
        if fam not in seen:
            j_sdk = f"{usd_2dp(j.usd_sdk):.2f}" if j.usd_sdk is not None else "—"
            lines.append(f"{fam:<20} {'DB: none':>7} {'':>12} {usd_2dp(j.usd):>14.2f} {'':>7} "
                         f"{'':>10} {j_sdk:>10} {'':>7}")
    return "\n".join(lines)
