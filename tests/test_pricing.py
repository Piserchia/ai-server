"""
List-price ledger + two-window reconcile core (Phase 1 B1; spec §2.8/§9). Pure.

Design of record: the P0 plan Task 16 tests, re-cut per the Phase-1 plan's B1
Deltas — `_ts` accepts epoch + ISO, a non-Anthropic provider is `unpriced`
with its provider named, `job_completed.model_served` outranks
`job_started.model`.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_pricing.py -q -p no:cacheprovider
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.runner.pricing import (
    LIST_PRICES,
    PRICES_AS_OF,
    JobCost,
    _ts,
    cache_write_buckets,
    family_for,
    implied_cache_write_rate,
    job_cost_from_events,
    lane_for,
    lane_seed,
    price_usage,
    quota_readings,
    render_db_delta,
    render_sdk_reconcile,
    render_table,
    render_weekly_allowance,
    summarize,
    summarize_windows,
    usd_2dp,
    weekly_allowance,
    write_lane_seed,
)


def _usage(inp=0, out=0, read=0, w1h=0, w5m=0):
    """The real prod shape: nested cache_creation + the flat key equal to their sum."""
    return {"input_tokens": inp, "output_tokens": out,
            "cache_read_input_tokens": read,
            "cache_creation_input_tokens": w1h + w5m,
            "cache_creation": {"ephemeral_1h_input_tokens": w1h,
                               "ephemeral_5m_input_tokens": w5m}}


# The FLEET median shape (spec §2.8: "fleet-median completed job 376 k cache-read /
# 47 k cache-write / 9.0 k output — a Sonnet atlas-report shape, ≈ $0.59"). It is
# NOT an Opus-5 job: §2.8 calls "median Opus 5 job ≈ $0.71" a mislabelling.
FLEET_MEDIAN = _usage(out=9_000, read=376_000, w1h=47_000)
# Today's real opus-5 atlas-swing-research job (spec §2.8, the DoneCard example).
OPUS5_REAL = _usage(out=47_000, read=2_400_000, w1h=111_000)
SINCE = datetime(2026, 9, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 10, 1, tzinfo=timezone.utc)
RESETS_AT = datetime(2026, 10, 2, tzinfo=timezone.utc)


def _events(model, usage, ts="2026-09-20T10:00:00+00:00", cost=None, skill="chat",
            channel="telegram", provider=None, model_served=None):
    """`cost` is the SDK's own figure → job_completed.sdk_cost_usd (round-3 #10:
    cost_usd_list in the same event is the RUNNER's computation, so reading it
    here would compare this module to itself). `provider` / `model_served`
    are the slice's additive fields (T4) — `None` = the field is absent, as on
    every pre-slice row."""
    started = {"ts": ts, "job_id": "x", "kind": "job_started", "model": model,
               "skill": skill, "job_kind": skill, "origin_channel": channel}
    done = {"ts": ts, "job_id": "x", "kind": "job_completed", "usage": usage,
            "duration_seconds": 5}
    if cost is not None:
        done["sdk_cost_usd"] = cost
    if provider is not None:
        started["provider"] = provider
        done["provider"] = provider
    if model_served is not None:
        done["model_served"] = model_served
    return [started, done]


def _quota_event(ts, util, resets="2026-10-02T00:00:00+00:00", kind="seven_day"):
    return {"ts": ts, "job_id": "x", "kind": "rate_limit_status", "status": "allowed_warning",
            "utilization": util, "resets_at": resets, "rate_limit_type": kind}


class TestPrices:
    def test_table_covers_every_family_the_fleet_uses(self):
        for fam in ("claude-opus-5", "claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-4-6",
                    "claude-fable-5", "claude-haiku-4-5", "claude-opus-5-5", "claude-sonnet-5"):
            assert fam in LIST_PRICES
        assert PRICES_AS_OF == "2026-09-24"

    def test_each_cache_write_bucket_is_priced_at_its_own_rate(self):
        # spec §2.8 / §2.3 row 007 (round-2 #19): 1-h writes at $10/M for Opus,
        # 5-m writes at $6.25/M; never one global rate.
        p = price_usage("claude-opus-5", _usage(w1h=1_000_000))
        assert p == Decimal(10)
        assert price_usage("claude-opus-5", _usage(w5m=1_000_000)) == Decimal("6.25")
        assert price_usage("claude-opus-5", _usage(w1h=1_000_000, w5m=1_000_000)) == Decimal("16.25")

    def test_flat_cache_creation_key_falls_back_to_the_1h_rate(self):
        # Older rows carry only the flat key; prod records 100 % of writes as 1-h,
        # so the flat value must NOT be priced at the 5-m rate.
        legacy = {"cache_creation_input_tokens": 1_000_000}
        assert price_usage("claude-opus-5", legacy) == Decimal(10)
        assert cache_write_buckets(legacy) == (1_000_000, 0)

    def test_cache_write_buckets_prefers_the_nested_object(self):
        # B2's usage_columns() reuses this: nested buckets win over the flat key
        # even when the flat key disagrees, and a Codex-mapped flat usage lands
        # on the 1-h arm.
        assert cache_write_buckets(_usage(w1h=700, w5m=300)) == (700, 300)
        assert cache_write_buckets({"cache_creation_input_tokens": 999,
                                    "cache_creation": {"ephemeral_5m_input_tokens": 5}}) == (0, 5)
        assert cache_write_buckets(None) == (0, 0)
        assert cache_write_buckets({"cache_creation_input_tokens": "bad"}) == (0, 0)

    def test_the_real_opus5_job_is_the_specs_3_49(self):
        # spec §2.8, as round 2 left it: "today's real opus-5
        # atlas-swing-research job (2.40 M read / 111 k 1-h write / 47 k out)
        # = $3.49, the DoneCard example in §4.2". Exact, at the 1-h rate:
        # 2.40M×$0.50 + 111k×$10 + 47k×$25 = 1.200 + 1.110 + 1.175 = $3.485
        # exactly; the spec's "$3.49" is that figure rounded half UP (usd_2dp),
        # which Decimal's default half-EVEN `round()` would print as 3.48.
        assert price_usage("claude-opus-5", OPUS5_REAL) == Decimal("3.485")
        assert usd_2dp(price_usage("claude-opus-5", OPUS5_REAL)) == Decimal("3.49")
        assert usd_2dp(Decimal("3.484")) == Decimal("3.48")
        # Round 1's "$0.71" for the same-shaped job used the 5-m rate.
        assert price_usage("claude-opus-5", OPUS5_REAL) != price_usage(
            "claude-opus-5", _usage(out=47_000, read=2_400_000, w5m=111_000))

    def test_the_fleet_median_SHAPE_prices_at_the_sonnet_1h_rate(self):
        # spec §2.8's median shape is 376 k cache-read / 47 k cache-write /
        # 9.0 k output on "a Sonnet atlas-report shape": 376k×$0.30 +
        # 47k×$6 + 9k×$15 = $0.5298. NOTE: §2.8's "fleet ≈ $0.59" is the
        # median of per-job COSTS, a different statistic from the cost of the
        # median shape — the report prints both (median_job and
        # median_usd_by_family).
        assert price_usage("claude-sonnet-4-6", FLEET_MEDIAN) == Decimal("0.5298")

    def test_longest_prefix_wins(self):
        assert family_for("claude-opus-5-5") == "claude-opus-5-5"
        assert family_for("claude-opus-5") == "claude-opus-5"
        assert family_for("claude-opus-5-20260401") == "claude-opus-5"
        assert family_for("claude-fable-5-1") == "claude-fable-5-1"
        assert family_for("claude-haiku-4-5-20251001") == "claude-haiku-4-5"
        assert family_for("CLAUDE-SONNET-4-6") == "claude-sonnet-4-6"

    def test_unknown_model_is_reported_not_priced(self):
        assert family_for("sonnet") is None
        assert family_for("claude-opus-9") is None and family_for("claude-opus-50") is None
        assert family_for("") is None and family_for(None) is None
        assert price_usage("sonnet", {"output_tokens": 5}) is None
        # A provider-qualified id is not a Claude family either.
        assert family_for("codex/gpt-5-codex") is None
        assert price_usage("gpt-5-codex", _usage(out=1_000_000)) is None

    def test_empty_usage_prices_at_zero_not_none(self):
        # A known family with no tokens is a $0 job, not an unpriced one.
        assert price_usage("claude-opus-5", {}) == Decimal(0)
        assert price_usage("claude-opus-5", None) == Decimal(0)


class TestLanes:
    def test_lane_for_is_the_documented_p0_approximation(self):
        assert lane_for("chat", "chat", "telegram") == "owner"
        assert lane_for("chat", "chat", "web") == "owner"
        assert lane_for("atlas-report", "atlas-report", "scheduler") == "atlas"
        assert lane_for("alpha-research", "alpha-research", "scheduler") == "atlas"
        assert lane_for("review-and-improve", "review-and-improve", "system") == "kernel"
        assert lane_for(None, "_writeback", "system") == "utility"
        assert lane_for("project-update-poll", "task", "scheduler") == "background"


class TestTs:
    def test_ts_accepts_epoch_and_iso(self):
        # Delta (2): prod `rate_limit_status.resets_at` is an EPOCH INTEGER;
        # the audit `ts` is ISO. Both must parse to the same aware instant.
        iso = _ts("2026-10-02T00:00:00+00:00")
        assert iso == RESETS_AT
        assert _ts("2026-10-02T00:00:00Z") == RESETS_AT
        assert _ts(int(RESETS_AT.timestamp())) == RESETS_AT
        assert _ts(float(RESETS_AT.timestamp())) == RESETS_AT
        assert _ts(str(int(RESETS_AT.timestamp()))) == RESETS_AT
        # A naive ISO stamp is read as UTC (never a naive datetime, which
        # would make every window comparison raise).
        naive = _ts("2026-10-02T00:00:00")
        assert naive == RESETS_AT and naive.tzinfo is not None
        for junk in (None, "", "soon", True, [], {}):
            assert _ts(junk) is None, junk


class TestLedger:
    def test_job_cost_from_events_and_summary(self):
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.485,
                                              skill="atlas-swing-research", channel="scheduler"))
        b = job_cost_from_events("b", _events("claude-sonnet-4-6", _usage(out=1000)))
        c = job_cost_from_events("c", _events("sonnet", _usage(out=10)))
        old = job_cost_from_events("d", _events("claude-opus-5", _usage(out=10),
                                                ts="2026-07-01T00:00:00+00:00"))
        assert isinstance(a, JobCost) and a.provider is None   # pre-slice row: no provider field
        rep = summarize([a, b, c, old], since=SINCE, until=UNTIL, days=30)
        assert rep.days == 30
        assert rep.totals.jobs == 3                      # `old` is outside the window
        assert [r.model for r in rep.unpriced] == ["sonnet"]
        opus = next(r for r in rep.per_model if r.model == "claude-opus-5")
        assert opus.jobs == 1 and opus.cache_read == 2_400_000
        assert opus.cache_write_1h == 111_000 and opus.cache_write_5m == 0
        assert usd_2dp(opus.usd) == Decimal("3.49")      # ONE usd column, each bucket at its rate
        assert opus.usd_sdk == Decimal("3.485") and opus.sdk_jobs == 1
        sonnet = next(r for r in rep.per_model if r.model == "claude-sonnet-4-6")
        assert sonnet.usd_sdk is None and sonnet.sdk_jobs == 0      # pre-P0 jobs carry no sdk_cost_usd
        assert set(rep.median_job) == {"cache_read", "cache_write_1h", "cache_write_5m",
                                       "output", "input"}
        assert usd_2dp(rep.median_usd_by_family["claude-opus-5"]) == Decimal("3.49")
        # The per-kind step table — the §2.8 "where the tokens go" view.
        kinds = {k.kind: k for k in rep.per_kind}
        assert kinds["atlas-swing-research"].jobs == 1
        assert kinds["atlas-swing-research"].tokens == 2_400_000 + 111_000 + 47_000
        assert rep.credit_signature is False
        table = render_table(rep)
        for needle in ("claude-opus-5", "unpriced", "sonnet", "atlas-swing-research",
                       "by kind", "30 d"):
            assert needle in table, needle
        d = rep.to_dict()
        assert d["days"] == 30 and d["prices_as_of"] == PRICES_AS_OF
        assert d["totals"]["jobs"] == 3 and isinstance(d["totals"]["usd"], str)

    def test_five_minute_writes_raise_the_credit_signature(self):
        # spec §2.8: "a cache_write_5m_tokens > 0 reading, since the TTL drop to
        # 5 m is itself the credits signature".
        a = job_cost_from_events("a", _events("claude-opus-5", _usage(w5m=1000)))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        assert rep.credit_signature is True
        assert "possible usage-credit overflow" in render_table(rep)

    def test_two_windows_in_one_pass(self):
        # spec §9 P0: "printing BOTH the trailing-30-d and trailing-7-d windows".
        recent = job_cost_from_events("r", _events("claude-opus-5", OPUS5_REAL,
                                                   ts="2026-09-28T10:00:00+00:00"))
        older = job_cost_from_events("o", _events("claude-opus-5", OPUS5_REAL,
                                                  ts="2026-09-10T10:00:00+00:00"))
        until = datetime(2026, 9, 30, tzinfo=timezone.utc)
        reps = summarize_windows([recent, older], until=until, windows=(30, 7))
        assert [r.days for r in reps] == [30, 7]
        assert reps[0].totals.jobs == 2 and reps[1].totals.jobs == 1
        assert [r.days for r in summarize_windows([recent], until=until)] == [30, 7]

    def test_lane_seed_is_trailing_7d_times_1_2(self, tmp_path):
        # spec §2.8/§2.5, round-2 #18: the seed is trailing-7-d × 1.2, re-seeded
        # weekly by THIS script — never the stale 30-d mean.
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL,
                                              skill="atlas-report", channel="scheduler"))
        b = job_cost_from_events("b", _events("claude-sonnet-4-6", FLEET_MEDIAN,
                                              skill="chat", channel="telegram"))
        rep = summarize([a, b], since=SINCE, until=UNTIL, days=7)
        seed = lane_seed(rep)
        assert Decimal(seed["atlas"]) == (Decimal("3.485") * Decimal("1.2")).quantize(Decimal("0.01"))
        assert Decimal(seed["owner"]) == (Decimal("0.5298") * Decimal("1.2")).quantize(Decimal("0.01"))
        out = write_lane_seed(rep, tmp_path / "telemetry" / "lane_budget_seed.json")
        import json
        doc = json.loads(out.read_text())
        assert doc["window_days"] == 7 and doc["multiplier"] == "1.2"
        assert doc["approximated_lanes"] is True and doc["weekly_budget_usd"] == seed

    def test_missing_job_started_gives_none(self):
        assert job_cost_from_events("x", [{"ts": "t", "job_id": "x", "kind": "job_completed", "usage": {}}]) is None
        assert job_cost_from_events("x", [{"ts": "t", "job_id": "x", "kind": "job_started", "model": "m"}]) is None

    def test_db_delta_table(self):
        # Four-tuples now: both cost columns per model (round-3 #10).
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.485))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        out = render_db_delta(rep, [("claude-opus-5", 1, Decimal("3.485"), Decimal("3.485")),
                                    ("claude-opus-4-7", 2, Decimal("1.0"), Decimal("1.0"))])
        assert "claude-opus-5" in out and "0.0%" in out
        assert "claude-opus-4-7" in out and "JSONL: none" in out   # rows only the DB has are shown, never hidden

    def test_model_served_outranks_requested_model(self):
        # Delta: pricing keys on job_completed.model_served FIRST, then
        # job_started.model — a bare-alias launch (`sonnet` from web/dispatch)
        # that the CLI served as a dated Sonnet id is priced as that family.
        jc = job_cost_from_events("a", _events("sonnet", FLEET_MEDIAN,
                                               model_served="claude-sonnet-4-6-20260101"))
        assert jc is not None
        assert jc.model == "claude-sonnet-4-6-20260101" and jc.requested_model == "sonnet"
        assert jc.family == "claude-sonnet-4-6"
        assert jc.usd == Decimal("0.5298")
        rep = summarize([jc], since=SINCE, until=UNTIL, days=30)
        assert rep.unpriced == [] and rep.per_model[0].model == "claude-sonnet-4-6"
        # No model_served (every pre-slice row) → the requested model.
        legacy = job_cost_from_events("b", _events("claude-opus-5", OPUS5_REAL))
        assert legacy.model == "claude-opus-5" and legacy.requested_model == "claude-opus-5"
        # A null model_served on a slice-era row is "absent", not the empty model.
        evts = _events("claude-opus-5", OPUS5_REAL)
        evts[1]["model_served"] = None
        assert job_cost_from_events("c", evts).model == "claude-opus-5"

    def test_non_anthropic_provider_is_unpriced_with_provider(self):
        # Review Focus 7 / Delta (3): a Codex job gets its tokens counted under
        # `unpriced` with the provider named — never a Claude price, even when
        # the served id looks like one. No Codex price table in Phase 1.
        codex = job_cost_from_events("a", _events(
            "gpt-5-codex", {"input_tokens": 10, "output_tokens": 1_000_000,
                            "cache_read_input_tokens": 5, "cache_creation_input_tokens": 7},
            provider="codex", model_served="gpt-5-codex", skill="atlas-build",
            channel="scheduler"))
        assert codex.provider == "codex" and codex.family is None and codex.usd is None
        assert codex.cache_write_1h == 7 and codex.cache_write_5m == 0   # flat key → 1-h arm
        lookalike = job_cost_from_events("b", _events(
            "claude-opus-5", OPUS5_REAL, provider="codex", model_served="claude-opus-5"))
        assert lookalike.family is None and lookalike.usd is None
        anthropic = job_cost_from_events("c", _events(
            "claude-opus-5", OPUS5_REAL, provider="anthropic", model_served="claude-opus-5"))
        assert anthropic.family == "claude-opus-5" and anthropic.usd is not None
        rep = summarize([codex, lookalike, anthropic], since=SINCE, until=UNTIL, days=30)
        assert rep.totals.jobs == 3
        assert [r.model for r in rep.per_model] == ["claude-opus-5"]
        assert sorted(r.model for r in rep.unpriced) == ["codex/claude-opus-5", "codex/gpt-5-codex"]
        unpriced = {r.model: r for r in rep.unpriced}
        assert unpriced["codex/gpt-5-codex"].output == 1_000_000
        assert unpriced["codex/gpt-5-codex"].usd == Decimal(0)
        assert rep.totals.usd == anthropic.usd       # the Codex tokens add nothing to $
        table = render_table(rep)
        assert "codex/gpt-5-codex" in table and "non-Anthropic provider" in table
        # The provider is not doubled when the id is already qualified.
        qualified = job_cost_from_events("d", _events("codex/gpt-5-codex", _usage(out=1),
                                                      provider="codex"))
        rep2 = summarize([qualified], since=SINCE, until=UNTIL, days=30)
        assert [r.model for r in rep2.unpriced] == ["codex/gpt-5-codex"]


class TestSdkReconcile:
    def test_computed_and_sdk_are_two_different_numbers(self):
        # Round-3 #10: before this, cost_usd_list WAS total_cost_usd, so the
        # exit criterion compared the SDK figure to itself and always passed.
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.485))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        row = rep.per_model[0]
        assert usd_2dp(row.usd) == Decimal("3.49")         # ours, from tokens
        assert row.usd_sdk == Decimal("3.485")             # the SDK's own
        out = render_sdk_reconcile(rep)
        assert "computed vs SDK" in out and "3.49" in out  # printed half-up, like the spec

    def test_a_5m_priced_sdk_figure_is_reported_with_its_implied_rate(self):
        # The failure mode the criterion exists for: the CLI prices cache writes
        # at the 5-m rate. Ours: 2.40M×$0.50 + 111k×$10 + 47k×$25 = $3.485.
        # Theirs at $6.25/M writes: 1.200 + 0.694 + 1.175 = $3.069.
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.069))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        out = render_sdk_reconcile(rep)
        assert "⚠" in out                                  # >1 % divergence flagged
        rate = implied_cache_write_rate(rep.per_model[0])
        assert rate == Decimal("6.25"), rate                # named, not guessed

    def test_reconcile_pairs_only_jobs_with_an_sdk_figure(self):
        # First prod run (2026-10-22): one of twelve opus-4-7 jobs carried
        # sdk_cost_usd, and the row compared that one SDK figure with the
        # computed sum of all twelve (−96.9 %, implied rate −6.63). The
        # comparison must be over the paired subset only.
        paired = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.069))
        unpaired = job_cost_from_events("b", _events("claude-opus-5", OPUS5_REAL))
        rep = summarize([paired, unpaired], since=SINCE, until=UNTIL, days=30)
        row = rep.per_model[0]
        assert row.jobs == 2 and row.sdk_jobs == 1
        assert usd_2dp(row.paired_usd) == Decimal("3.49")  # the paired job only
        assert usd_2dp(row.usd) == Decimal("6.97")         # the window total, untouched
        assert implied_cache_write_rate(row) == Decimal("6.25")
        out = render_sdk_reconcile(rep)
        assert "PAIRED" in out and "    1 " in out and "3.49" in out and "6.97" not in out
        assert "-11.9%" in out                              # 3.069 vs 3.485, not vs 6.97

    def test_within_one_percent_is_not_flagged(self):
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL, cost=3.49))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        assert "⚠" not in render_sdk_reconcile(rep)

    def test_rows_without_an_sdk_figure_or_writes_have_no_implied_rate(self):
        a = job_cost_from_events("a", _events("claude-opus-5", OPUS5_REAL))
        rep = summarize([a], since=SINCE, until=UNTIL, days=30)
        assert implied_cache_write_rate(rep.per_model[0]) is None
        assert "—" in render_sdk_reconcile(rep)
        b = job_cost_from_events("b", _events("claude-opus-5", _usage(out=1_000), cost=0.025))
        rep = summarize([b], since=SINCE, until=UNTIL, days=30)
        assert implied_cache_write_rate(rep.per_model[0]) is None


class TestWeeklyAllowance:
    def test_the_series_brackets_the_allowance_in_dollars(self):
        # spec §2.8's own arithmetic: utilization 0.25 at ≈ $69 spent and 0.58
        # at ≈ $120 bracket the week at ≈ $207–275, marginal ≈ $155. Round 3
        # replaced round 2's single-reading "≈ 4 days" with exactly this.
        reads = quota_readings([_quota_event("2026-09-25T13:57:00+00:00", 0.25),
                                _quota_event("2026-09-27T10:32:00+00:00", 0.58)])
        assert len(reads) == 2 and reads[0].resets_at is not None
        jobs = [job_cost_from_events(f"j{i}", _events(
                    "claude-opus-5", _usage(out=2_760_000),      # $69 at $25/M output
                    ts="2026-09-25T12:00:00+00:00"))
                for i in range(1)]
        jobs += [job_cost_from_events("k", _events(
                    "claude-opus-5", _usage(out=2_040_000),      # +$51 ⇒ $120 total
                    ts="2026-09-26T12:00:00+00:00"))]
        cal = weekly_allowance(jobs, reads)
        assert cal is not None
        assert cal.window_opens_at == datetime(2026, 9, 25, tzinfo=timezone.utc)
        assert cal.implied_usd == (Decimal("276"), Decimal("207"))
        assert cal.marginal_usd == Decimal("155")
        out = render_weekly_allowance(cal)
        assert "$200/week" in out and "RE-DERIVE" in out
        d = cal.to_dict()
        assert d["marginal_usd"] == "155" and d["working_usd"] == "200"
        assert d["window_opens_at"] == "2026-09-25T00:00:00+00:00" and len(d["points"]) == 2

    def test_epoch_resets_at_opens_the_same_window(self):
        # Delta (2): prod's resets_at is an epoch int; the window must open at
        # the same instant as for the ISO form.
        epoch = int(RESETS_AT.timestamp())
        reads = quota_readings([_quota_event("2026-09-25T13:57:00+00:00", 0.25, resets=epoch)])
        assert reads[0].resets_at == RESETS_AT
        cal = weekly_allowance([], reads)
        assert cal is not None and cal.window_opens_at == datetime(2026, 9, 25, tzinfo=timezone.utc)
        assert cal.implied_usd == (Decimal("0"),) and cal.marginal_usd is None

    def test_readings_from_an_earlier_window_are_excluded(self):
        # First prod run (2026-10-22): readings from the 09-25→10-02 window were
        # scored against the 10-16 window's opening and printed "$0/week". Only
        # readings sharing the newest resets_at belong to the current window.
        old = [_quota_event("2026-09-25T13:57:00+00:00", 0.25),
               _quota_event("2026-09-27T10:32:00+00:00", 0.58)]
        cur = [_quota_event("2026-10-17T12:00:00+00:00", 0.20,
                            resets="2026-10-23T00:00:00+00:00"),
               _quota_event("2026-10-19T12:00:00+00:00", 0.40,
                            resets="2026-10-23T00:00:00+00:00")]
        reads = quota_readings(old + cur)
        jobs = [job_cost_from_events("c1", _events(
                    "claude-opus-5", _usage(out=1_600_000),      # $40 at $25/M output
                    ts="2026-10-17T06:00:00+00:00")),
                job_cost_from_events("c2", _events(
                    "claude-opus-5", _usage(out=1_600_000),      # +$40 ⇒ $80
                    ts="2026-10-18T06:00:00+00:00"))]
        cal = weekly_allowance(jobs, reads)
        assert cal is not None
        assert cal.window_opens_at == datetime(2026, 10, 16, tzinfo=timezone.utc)
        assert [p[0].isoformat() for p in cal.points] == [
            "2026-10-17T12:00:00+00:00", "2026-10-19T12:00:00+00:00"]
        assert cal.implied_usd == (Decimal("200"), Decimal("200"))
        assert cal.marginal_usd == Decimal("200")

    def test_five_hour_readings_are_not_the_weekly_bar(self):
        assert quota_readings([_quota_event("2026-09-25T13:57:00+00:00", 0.96,
                                            kind="five_hour")]) == []
        # ... and neither are readings with no / zero / junk utilization.
        assert quota_readings([_quota_event("2026-09-25T13:57:00+00:00", None),
                               _quota_event("2026-09-25T13:57:00+00:00", 0),
                               _quota_event("2026-09-25T13:57:00+00:00", "n/a"),
                               {"kind": "job_started", "ts": "2026-09-25T13:57:00+00:00"}]) == []

    def test_no_readings_is_stated_not_assumed(self):
        assert weekly_allowance([], []) is None
        assert "unre-derived" in render_weekly_allowance(None)
        # A reading without resets_at cannot open a window either.
        reads = quota_readings([_quota_event("2026-09-25T13:57:00+00:00", 0.25, resets=None)])
        assert len(reads) == 1 and reads[0].resets_at is None
        assert weekly_allowance([], reads) is None


# ── B4: the CLI over a fixture JSONL dir ─────────────────────────────────────

import importlib.util  # noqa: E402
import json as _json  # noqa: E402
from datetime import timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CLI_PATH = REPO / "scripts" / "cost-reconcile.py"


@pytest.fixture(scope="module")
def cli():
    """`scripts/cost-reconcile.py` loaded as a module (hyphenated file name →
    importlib, not `import`). `main(argv, *, db_rows=)` is the entry point;
    `db_rows` is the injectable DB leg so no test ever opens Postgres."""
    spec = importlib.util.spec_from_file_location("cost_reconcile", CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_job(audit_dir: Path, job_id: str, model: str, usage: dict, *, days_ago: float,
               skill: str = "chat", channel: str = "telegram", cost=None, provider=None,
               model_served=None, extra: list[dict] | None = None) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    events = _events(model, usage, ts=ts, cost=cost, skill=skill, channel=channel,
                     provider=provider, model_served=model_served)
    for e in events:
        e["job_id"] = job_id
    events = events[:1] + (extra or []) + events[1:]
    (audit_dir / f"{job_id}.jsonl").write_text(
        "\n".join(_json.dumps(e) for e in events) + "\n", encoding="utf-8")


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    """Three completed jobs: a scheduler-born opus-5 atlas job 2 d ago (with an
    SDK figure and a seven_day quota reading), a telegram-born sonnet job 15 d
    ago (only in the 30-d window) and a Codex job 1 d ago (unpriced). INDEX.jsonl is the audit index, not a
    job trace, and carries a complete job_started/job_completed pair that must
    NOT be counted."""
    now = datetime.now(timezone.utc)
    resets = (now + timedelta(days=1)).isoformat()
    reading = {"ts": (now - timedelta(days=2, hours=1)).isoformat(), "job_id": "a",
               "kind": "rate_limit_status", "status": "allowed_warning",
               "utilization": 0.25, "resets_at": resets, "rate_limit_type": "seven_day"}
    _write_job(tmp_path, "a", "claude-opus-5", OPUS5_REAL, days_ago=2,
               skill="atlas-swing-research", channel="scheduler", cost=3.49, extra=[reading])
    _write_job(tmp_path, "b", "claude-sonnet-4-6", FLEET_MEDIAN, days_ago=15,
               skill="atlas-report")
    _write_job(tmp_path, "c", "gpt-5-codex", _usage(inp=1000, out=500), days_ago=1,
               skill="server-patch", provider="codex", model_served="gpt-5-codex")
    index_events = _events("claude-opus-5", OPUS5_REAL, ts=(now - timedelta(days=1)).isoformat())
    (tmp_path / "INDEX.jsonl").write_text(
        "\n".join(_json.dumps(e) for e in index_events) + "\n", encoding="utf-8")
    return tmp_path


class TestCli:
    def test_default_windows_print_both_blocks_and_the_per_kind_step(self, cli, ledger, capsys):
        rc = cli.main(["--audit-dir", str(ledger)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "== trailing 30 d ==" in out and "== trailing 7 d ==" in out
        assert out.index("== trailing 30 d ==") < out.index("== trailing 7 d ==")
        assert out.count("-- by kind (the §2.8 step) --") == 2
        assert "atlas-swing-research" in out and "atlas-report" in out
        assert "codex/gpt-5-codex" in out                      # unpriced, provider named
        assert out.count("computed vs SDK") == 2
        assert "-- weekly allowance" in out and "unre-derived" not in out
        assert "DB reconcile" not in out and "lane budget seed" not in out

    def test_json_shape(self, cli, ledger, capsys):
        rc = cli.main(["--audit-dir", str(ledger), "--json"])
        out = capsys.readouterr().out
        assert rc == 0
        data = _json.loads(out)
        assert set(data) >= {"windows", "weekly_allowance", "credit_signature", "prices_as_of",
                             "audit_dir", "until"}
        assert [w["days"] for w in data["windows"]] == [30, 7]
        assert data["windows"][0]["totals"]["jobs"] == 3        # a + b + c, never INDEX.jsonl
        assert data["windows"][1]["totals"]["jobs"] == 2        # a + c
        assert [r["model"] for r in data["windows"][1]["unpriced"]] == ["codex/gpt-5-codex"]
        assert data["credit_signature"] is False
        assert data["weekly_allowance"]["window_opens_at"] is not None
        assert data["prices_as_of"] == PRICES_AS_OF
        assert "db" not in data and "lane_seed" not in data

    def test_days_alias_is_one_window(self, cli, ledger, capsys):
        assert cli.main(["--audit-dir", str(ledger), "--days", "7", "--json"]) == 0
        data = _json.loads(capsys.readouterr().out)
        assert [w["days"] for w in data["windows"]] == [7]

    def test_windows_list_is_honoured_in_order(self, cli, ledger, capsys):
        assert cli.main(["--audit-dir", str(ledger), "--windows", "1, 90", "--json"]) == 0
        data = _json.loads(capsys.readouterr().out)
        assert [w["days"] for w in data["windows"]] == [1, 90]

    def test_exit_1_on_the_credit_signature(self, cli, ledger, capsys):
        _write_job(ledger, "d", "claude-opus-5", _usage(out=100, read=1000, w5m=500), days_ago=3)
        rc = cli.main(["--audit-dir", str(ledger)])
        out = capsys.readouterr().out
        assert rc == 1
        assert "5-minute cache writes present" in out
        assert cli.main(["--audit-dir", str(ledger), "--json"]) == 1
        assert _json.loads(capsys.readouterr().out)["credit_signature"] is True

    def test_missing_audit_dir_exits_2(self, cli, tmp_path, capsys):
        rc = cli.main(["--audit-dir", str(tmp_path / "nope")])
        err = capsys.readouterr().err
        assert rc == 2 and "no such audit dir" in err

    def test_empty_audit_dir_is_a_report_not_a_failure(self, cli, tmp_path, capsys):
        assert cli.main(["--audit-dir", str(tmp_path), "--json"]) == 0
        data = _json.loads(capsys.readouterr().out)
        assert data["windows"][0]["totals"]["jobs"] == 0
        assert data["weekly_allowance"] is None

    def test_seed_lane_budgets_writes_the_7d_seed(self, cli, ledger, tmp_path, capsys):
        out_path = tmp_path / "telemetry" / "lane_budget_seed.json"
        rc = cli.main(["--audit-dir", str(ledger), "--seed-lane-budgets", str(out_path)])
        out = capsys.readouterr().out
        assert rc == 0
        seed = _json.loads(out_path.read_text())
        assert seed["window_days"] == 7                       # the SHORTEST window, never 30
        assert seed["multiplier"] == "1.2" and seed["approximated_lanes"] is True
        # the approximated lanes: the scheduler-born atlas-* job → `atlas`, the
        # telegram-born Codex job → `owner` ($0, unpriced); the sonnet job is
        # 15 d old and outside the 7-d seed window
        assert set(seed["weekly_budget_usd"]) == {"atlas", "owner"}
        expected = (price_usage("claude-opus-5", OPUS5_REAL) * Decimal("1.2")).quantize(Decimal("0.01"))
        assert Decimal(seed["weekly_budget_usd"]["atlas"]) == expected
        assert seed["weekly_budget_usd"]["owner"] == "0.00"
        assert "lane budget seed (trailing 7 d × 1.2)" in out
        assert str(out_path) in out
        # the same values are printed as a table
        for lane, usd in seed["weekly_budget_usd"].items():
            assert lane in out and usd in out

    def test_seed_default_path_is_under_the_server_root(self, cli, ledger, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(cli.settings, "server_root", tmp_path)
        assert cli.main(["--audit-dir", str(ledger), "--seed-lane-budgets", "--json"]) == 0
        data = _json.loads(capsys.readouterr().out)
        expected = tmp_path / "volumes" / "telemetry" / "lane_budget_seed.json"
        assert expected.is_file()
        assert data["lane_seed"]["path"] == str(expected)
        assert data["lane_seed"]["window_days"] == 7
        assert data["lane_seed"]["weekly_budget_usd"] == _json.loads(expected.read_text())["weekly_budget_usd"]

    def test_db_leg_uses_the_injected_rows_for_both_cost_columns(self, cli, ledger, capsys):
        calls: list[tuple[datetime, datetime]] = []

        def fake_rows(since, until):
            calls.append((since, until))
            return [("claude-opus-5-20260901", 1, Decimal("3.4850"), Decimal("3.49")),
                    ("gpt-5-codex", 1, None, None)]

        rc = cli.main(["--audit-dir", str(ledger), "--db"], db_rows=fake_rows)
        out = capsys.readouterr().out
        assert rc == 0
        assert len(calls) == 2 and all(isinstance(s, datetime) and s < u for s, u in calls)
        assert (calls[0][1] - calls[0][0]).days == 30 and (calls[1][1] - calls[1][0]).days == 7
        assert "-- DB reconcile, trailing 30 d --" in out and "-- DB reconcile, trailing 7 d --" in out
        assert "DB computed" in out and "JSONL SDK" in out
        assert "claude-opus-5 " in out                          # family, not the dated id

    def test_db_leg_in_json(self, cli, ledger, capsys):
        rows = [("claude-opus-5", 1, Decimal("3.4850"), Decimal("3.49"))]
        assert cli.main(["--audit-dir", str(ledger), "--db", "--json"],
                        db_rows=lambda s, u: rows) == 0
        data = _json.loads(capsys.readouterr().out)
        assert [d["days"] for d in data["db"]] == [30, 7]
        assert data["db"][0]["rows"] == [{"model": "claude-opus-5", "jobs": 1,
                                          "cost_usd_list": "3.4850", "sdk_cost_usd": "3.49"}]
        assert "DB computed" in data["db"][0]["table"]

    def test_db_is_never_touched_without_the_flag(self, cli, ledger, capsys):
        def boom(since, until):
            raise AssertionError("Postgres opened without --db")
        assert cli.main(["--audit-dir", str(ledger)], db_rows=boom) == 0

    def test_db_leg_failure_is_not_the_credit_signature(self, cli, ledger, capsys):
        # Review round 1 (major): Postgres down / DSN wrong / pre-008 schema
        # must NOT exit 1 — rc=1 is reserved for `credit_signature`, and the
        # wrapper turns it into the "check claude.ai billing" DM. Infrastructure
        # failures get rc=3 and a stderr line, with no traceback as rc=1.
        def down(since, until):
            raise ConnectionRefusedError("connection refused")

        rc = cli.main(["--audit-dir", str(ledger), "--db"], db_rows=down)
        cap = capsys.readouterr()
        assert rc == 3
        assert "DB leg failed: ConnectionRefusedError: connection refused" in cap.err
        assert "5-minute cache writes present" not in cap.out
        # the JSON path fails the same way, and never claims the signature
        rc = cli.main(["--audit-dir", str(ledger), "--db", "--json"], db_rows=down)
        cap = capsys.readouterr()
        assert rc == 3 and "DB leg failed" in cap.err
        assert '"credit_signature": true' not in cap.out

    def test_db_sql_reads_both_cost_columns_keyed_on_the_served_model(self, cli):
        sql = " ".join(cli.DB_SQL.split())
        assert "SUM(cost_usd_list)" in sql and "SUM(sdk_cost_usd)" in sql
        assert "COALESCE(model_served, resolved_model" in sql     # the JSONL leg's precedence
        assert "status = 'completed'" in sql and "completed_at >= :since" in sql
        assert "completed_at < :until" in sql

    def test_db_leg_disposes_the_engine_per_run(self):
        # Review round 2 (major): `main` calls `db_rows` once PER WINDOW and
        # `_db_rows` wraps each call in its own `asyncio.run`. `src.db.engine`
        # is a module-level pooled AsyncEngine; a connection checked out in the
        # first loop is handed back by the pool inside the second loop and
        # asyncpg raises "attached to a different loop" — the 7-d DB leg would
        # exit 3 every Monday. SQLAlchemy's rule: dispose the engine before
        # reusing it under a new event loop. The injected-rows tests cannot
        # see the real leg, so its one invariant is pinned at source level:
        # `_db_rows_async` ends in `finally: await engine.dispose()`.
        import ast
        tree = ast.parse(CLI_PATH.read_text())
        fn = next(n for n in tree.body
                  if isinstance(n, ast.AsyncFunctionDef) and n.name == "_db_rows_async")
        tries = [n for n in ast.walk(fn) if isinstance(n, ast.Try) and n.finalbody]
        assert tries, "_db_rows_async has no try/finally"

        def _is_engine_dispose(node: ast.AST) -> bool:
            return (isinstance(node, ast.Await)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute)
                    and node.value.func.attr == "dispose"
                    and isinstance(node.value.func.value, ast.Name)
                    and node.value.func.value.id == "engine")

        assert any(_is_engine_dispose(x) for t in tries for stmt in t.finalbody
                   for x in ast.walk(stmt)), "no `await engine.dispose()` in a finally"
        # the session block itself is inside the guarded body, not after it
        guarded = [n for t in tries for stmt in t.body for n in ast.walk(stmt)
                   if isinstance(n, ast.AsyncWith)]
        assert guarded, "the async_session block is not inside the try body"

    def test_cli_imports_nothing_from_the_db_at_module_level(self):
        # The DB engine is built on `import src.db`; the hand-run and the
        # timer must not open Postgres unless `--db` was asked for, so the
        # only `src.db` / `sqlalchemy` imports are inside the --db function.
        import ast
        tree = ast.parse(CLI_PATH.read_text())
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module or "" for n in top if isinstance(n, ast.ImportFrom)}
        assert not any(n == "src.db" or n.startswith("sqlalchemy") for n in names), names


class TestServedModelMismatch:
    """A `model_served` of a different family than the request is not a pricing
    basis (prod 2026-10-22..28: the runner wrote the CLI's own auxiliary haiku
    entry there for 39 Opus/Sonnet jobs, pricing them at Haiku rates)."""

    def _events(self, requested, served, usage):
        # Same ts as the module's other fixtures, i.e. inside SINCE..UNTIL.
        return [{"kind": "job_started", "model": requested, "skill": "chat"},
                {"kind": "job_completed", "model_served": served, "usage": usage,
                 "ts": "2026-09-20T10:00:00+00:00"}]

    def test_a_different_family_is_priced_at_the_request(self):
        jc = job_cost_from_events("j", self._events(
            "claude-opus-5", "claude-haiku-4-5-20251001", OPUS5_REAL))
        assert jc.model == "claude-opus-5" and jc.family == "claude-opus-5"
        assert jc.requested_model == "claude-opus-5" and jc.served_mismatch is True
        haiku = price_usage("claude-haiku-4-5", OPUS5_REAL)
        assert jc.usd > haiku                      # not the haiku rate any more

    def test_a_dated_snapshot_of_the_same_family_still_wins(self):
        jc = job_cost_from_events("j", self._events(
            "claude-opus-4-7", "claude-opus-4-7-20260301", OPUS5_REAL))
        assert jc.model == "claude-opus-4-7-20260301" and jc.served_mismatch is False
        assert jc.family == "claude-opus-4-7"

    def test_served_with_no_request_is_still_used(self):
        jc = job_cost_from_events("j", self._events("", "claude-sonnet-4-6", OPUS5_REAL))
        assert jc.model == "claude-sonnet-4-6" and jc.served_mismatch is False

    def test_a_bare_alias_request_is_still_priced_from_the_served_id(self):
        # The reason model_served is read at all: `sonnet` has no family, so a
        # dated Sonnet id is a refinement, not a mismatch.
        jc = job_cost_from_events("j", self._events(
            "sonnet", "claude-sonnet-4-6-20260101", OPUS5_REAL))
        assert jc.model == "claude-sonnet-4-6-20260101" and jc.served_mismatch is False
        assert jc.family == "claude-sonnet-4-6"

    def test_the_mismatch_is_counted_and_rendered_never_silent(self):
        jobs = [job_cost_from_events("a", self._events(
                    "claude-opus-5", "claude-haiku-4-5-20251001", OPUS5_REAL)),
                job_cost_from_events("b", self._events(
                    "claude-opus-5", "claude-opus-5", OPUS5_REAL))]
        rep = summarize(jobs, since=SINCE, until=UNTIL, days=30)
        assert rep.served_mismatches == 1
        assert rep.to_dict()["served_mismatches"] == 1
        out = render_sdk_reconcile(rep)
        assert "different family than the request" in out
        # Both jobs land in the opus-5 row — the bogus haiku row is gone.
        assert [r.model for r in rep.per_model] == ["claude-opus-5"]
        assert rep.per_model[0].jobs == 2
