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
