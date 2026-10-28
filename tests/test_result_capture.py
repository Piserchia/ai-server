"""
Pure tests for src/runner/result_capture.py — the typed ResultMessage capture
that replaces `usage = getattr(message, "usage", {})` in session._run_in_process
(Observability Phase 1 B2; design of record P0 plan Task 2, re-cut per the
Phase-1 plan's B2 Deltas: 15-value TERMINAL_REASONS (D-P1-1), no
`parse_cli_version`, `API_RETRY_TO_TERMINAL` as the one alias table, and the
capture-free `usage_columns` both lanes stamp their token columns through).

No SDK import: a SimpleNamespace with the ResultMessage field names
(claude_agent_sdk/types.py ResultMessage) stands in for the message.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_result_capture.py -q -p no:cacheprovider
"""

from __future__ import annotations

import ast
import asyncio
import inspect
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.runner import result_capture
from src.runner.result_capture import (
    API_RETRY_TO_TERMINAL,
    ENFORCEMENT_CATEGORIES,
    TERMINAL_REASONS,
    ResultCapture,
    capture_result_message,
    derive_terminal_reason,
    requested_matches_served,
    result_columns,
    same_model,
    served_model_violation,
    terminal_reason_for_exception,
    usage_columns,
    usage_is_empty,
)

# Real prod shape (verified on prod's audit log 2026-09-27): the nested
# cache_creation object carries the TTL split and the flat
# cache_creation_input_tokens equals the 1-h figure to the token.
REAL_USAGE = {
    "input_tokens": 15, "output_tokens": 9363,
    "cache_read_input_tokens": 379675, "cache_creation_input_tokens": 12000,
    "cache_creation": {"ephemeral_1h_input_tokens": 12000,
                       "ephemeral_5m_input_tokens": 0},
    "server_tool_use": {"web_search_requests": 0}, "service_tier": "standard",
}
# An older row with no nested object: the flat count must land in the 1-h arm.
LEGACY_USAGE = {
    "input_tokens": 15, "output_tokens": 9363,
    "cache_read_input_tokens": 379675, "cache_creation_input_tokens": 12000,
}
# The credits signature: TTL dropped to 5 m (spec §2.8 metered-spend tripwires).
FIVE_MIN_USAGE = dict(REAL_USAGE, cache_creation={
    "ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 12000})
ZERO_USAGE = {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


def _msg(**over):
    base = dict(
        subtype="success", duration_ms=201000, duration_api_ms=180500, is_error=False,
        num_turns=12, session_id="s", stop_reason="end_turn", total_cost_usd=0.0812,
        usage=REAL_USAGE, result="TASK_COMPLETE: done", structured_output=None,
        model_usage={"claude-sonnet-4-6": {"inputTokens": 15, "outputTokens": 9363}},
        permission_denials=[], errors=None, api_error_status=None, uuid="u",
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestCapture:
    def test_full_message_captured(self):
        cap = capture_result_message(_msg())
        assert cap.num_turns == 12
        assert cap.duration_api_ms == 180500
        assert cap.total_cost_usd == pytest.approx(0.0812)
        assert cap.input_tokens == 15 and cap.output_tokens == 9363
        assert cap.cache_read_tokens == 379675
        assert cap.cache_write_1h_tokens == 12000 and cap.cache_write_5m_tokens == 0
        assert cap.model_served == "claude-sonnet-4-6"
        assert cap.usage_empty is False
        assert cap.permission_denials == 0
        assert cap.api_retry_error is None

    def test_ephemeral_1h_is_the_1h_arm_and_the_flat_key_falls_back_to_it(self):
        # Spec §9 P0 test gate: "the 1-h cache-write rate is used when
        # ephemeral_1h_input_tokens > 0" — the split has to survive capture,
        # and a legacy row with no nested object must not be priced at 5 m.
        assert capture_result_message(_msg()).cache_write_1h_tokens == 12000
        legacy = capture_result_message(_msg(usage=LEGACY_USAGE))
        assert legacy.cache_write_1h_tokens == 12000
        assert legacy.cache_write_5m_tokens == 0

    def test_five_minute_writes_are_reported_separately(self):
        # A non-zero 5-m count is the usage-credits signature (spec §2.8), so it
        # must never be folded into the 1-h column.
        cap = capture_result_message(_msg(usage=FIVE_MIN_USAGE))
        assert cap.cache_write_1h_tokens == 0 and cap.cache_write_5m_tokens == 12000

    def test_missing_optional_fields_default(self):
        # An older CLI shape: no model_usage/api_error_status/permission_denials attrs at all.
        cap = capture_result_message(SimpleNamespace(subtype="success", is_error=False,
                                                     usage=ZERO_USAGE, result=""))
        assert cap.model_usage == {} and cap.model_served is None
        assert cap.api_error_status is None and cap.num_turns is None
        assert cap.usage_empty is True

    def test_non_dict_usage_is_ignored(self):
        cap = capture_result_message(_msg(usage="garbage", model_usage=None))
        assert cap.usage == {} and cap.model_usage == {}

    def test_api_retry_error_rides_the_capture(self):
        # Not a ResultMessage field: the session's last system/api_retry
        # category travels on the same object as everything else.
        cap = capture_result_message(_msg(), api_retry_error="rate_limit")
        assert cap.api_retry_error == "rate_limit"
        assert capture_result_message(_msg(), api_retry_error="").api_retry_error is None

    def test_capture_is_frozen(self):
        cap = capture_result_message(_msg())
        with pytest.raises(Exception):
            cap.num_turns = 1  # type: ignore[misc]

    def test_module_imports_no_sdk(self):
        # Pure by construction: the module must stay importable without the
        # SDK so the terminal-reason logic is testable with a fake message.
        src = Path(result_capture.__file__).read_text()
        names = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        assert not any(n.startswith("claude_agent_sdk") for n in names)
        assert not any(n.startswith("src.runner.session") for n in names)


class TestTerminalReason:
    def test_vocabulary_matches_spec(self):
        # spec §2.4 ExecResult.terminal_reason (13) + the two the tree already
        # stamps and the gate/badges pin (D-P1-1): 15.
        assert TERMINAL_REASONS == (
            "ok", "max_turns", "interrupted", "timeout", "api_error",
            "rate_limited", "auth_expired", "unrecognized_model",
            "account_on_hold", "oauth_revoked", "billing_error",
            "provider_refused", "error", "review_blocked", "publish_failed",
        )
        assert len(set(TERMINAL_REASONS)) == 15

    @pytest.mark.parametrize("over,expected", [
        ({}, "ok"),
        ({"api_error_status": 529, "is_error": True}, "api_error"),
        ({"api_error_status": 500, "is_error": True}, "api_error"),
        ({"api_error_status": 429, "is_error": True}, "rate_limited"),
        ({"api_error_status": 401, "is_error": True}, "auth_expired"),
        ({"api_error_status": 403, "is_error": True}, "auth_expired"),
        ({"subtype": "error_max_turns", "is_error": True}, "max_turns"),
        ({"stop_reason": "max_turns"}, "max_turns"),
        ({"subtype": "error_during_execution", "is_error": True}, "error"),
    ])
    def test_typed_fields_drive_reason(self, over, expected):
        assert derive_terminal_reason(capture_result_message(_msg(**over))) == expected

    def test_banner_belt_when_typed_fields_silent(self):
        # The 143c8cfb shape: is_error unset, no api_error_status, banner text.
        cap = capture_result_message(_msg(usage=ZERO_USAGE, result="API Error: 529 Overloaded."))
        assert derive_terminal_reason(cap, banner_terminal=True) == "api_error"
        assert derive_terminal_reason(cap, banner_terminal=False) == "ok"

    # ── The enforcement mapping (spec §2.4 / P0 round-3 #M16): the vendor's own
    # `error` CATEGORY from system/api_retry, never an HTTP status. An account
    # hold and a 403 are indistinguishable by status, and `billing_error` is the
    # direct signal §2.8's credit-overflow chain is built to catch.
    @pytest.mark.parametrize("category,expected", [
        ("account_on_hold", "account_on_hold"),
        ("oauth_org_not_allowed", "oauth_revoked"),
        ("billing_error", "billing_error"),
        ("authentication_failed", "auth_expired"),
        ("rate_limit", "rate_limited"),
        ("overloaded", "api_error"),
    ])
    def test_api_retry_category_maps_to_terminal_reason(self, category, expected):
        cap = capture_result_message(_msg(is_error=True, result="failed"),
                                     api_retry_error=category)
        assert derive_terminal_reason(cap) == expected

    @pytest.mark.parametrize("category", ["overloaded", "rate_limit", "authentication_failed"])
    def test_recovered_api_retry_on_a_success_is_ok(self, category):
        # The CLI emits system/api_retry before the retry's outcome is known;
        # a session that then finished cleanly is `ok` (spec §2.4) — the audit
        # `api_retry` row keeps the recovered retry. The same category on a
        # failed capture is the mapped reason (whole-tier review 2026-10-22).
        assert derive_terminal_reason(capture_result_message(_msg(), api_retry_error=category)) == "ok"
        cap = capture_result_message(_msg(is_error=True, result="failed"), api_retry_error=category)
        assert derive_terminal_reason(cap) == API_RETRY_TO_TERMINAL[category]

    @pytest.mark.parametrize("category,expected", [
        ("account_on_hold", "account_on_hold"),
        ("oauth_org_not_allowed", "oauth_revoked"),
        ("billing_error", "billing_error"),
    ])
    def test_enforcement_category_maps_even_on_a_success_shape(self, category, expected):
        # The plan's "outranks the status" guarantee is independent of
        # is_error: a vendor enforcement category is the reason regardless of
        # what the ResultMessage looks like (session._run_in_process raises on
        # it before this runs, but the mapping must not depend on that).
        assert derive_terminal_reason(capture_result_message(_msg(), api_retry_error=category)) == expected

    def test_api_retry_category_outranks_the_http_status(self):
        # A 403 with an account_on_hold category is a hold, not an expiry: the
        # two need different owner actions (spec §2.4 holds every lane but
        # `owner` and DMs an ApprovalCard).
        held = capture_result_message(_msg(api_error_status=403, is_error=True),
                                      api_retry_error="account_on_hold")
        assert derive_terminal_reason(held) == "account_on_hold"
        plain = capture_result_message(_msg(api_error_status=403, is_error=True))
        assert derive_terminal_reason(plain) == "auth_expired"

    def test_unknown_api_retry_category_falls_through(self):
        cap = capture_result_message(_msg(api_error_status=429, is_error=True),
                                     api_retry_error="something_new")
        assert derive_terminal_reason(cap) == "rate_limited"

    def test_category_is_normalised(self):
        cap = capture_result_message(_msg(is_error=True), api_retry_error="  Rate_Limit ")
        assert derive_terminal_reason(cap) == "rate_limited"

    def test_mapping_table_is_the_only_source(self):
        # One table, six vendor categories, every value a TERMINAL_REASON.
        assert API_RETRY_TO_TERMINAL == {
            "rate_limit": "rate_limited",
            "overloaded": "api_error",
            "account_on_hold": "account_on_hold",
            "oauth_org_not_allowed": "oauth_revoked",
            "billing_error": "billing_error",
            "authentication_failed": "auth_expired",
        }
        assert set(API_RETRY_TO_TERMINAL.values()) <= set(TERMINAL_REASONS)
        assert ENFORCEMENT_CATEGORIES == {"account_on_hold", "oauth_revoked", "billing_error"}
        assert ENFORCEMENT_CATEGORIES <= set(API_RETRY_TO_TERMINAL.values())
        # No second alias table anywhere in the module.
        src = Path(result_capture.__file__).read_text()
        assert src.count('"oauth_org_not_allowed"') == 1

    def test_every_reason_fits_column(self):
        # jobs.terminal_reason is String(32) (migration 007).
        assert all(len(r) <= 32 for r in TERMINAL_REASONS)

    def test_api_retry_outputs_are_all_in_vocabulary(self):
        for category in API_RETRY_TO_TERMINAL:
            cap = capture_result_message(_msg(), api_retry_error=category)
            assert derive_terminal_reason(cap) in TERMINAL_REASONS


def test_codex_terminal_reasons_are_a_subset():
    # The Codex lane keeps its own `ExecResult.terminal_reason`; its vocabulary
    # must be a subset of the one column vocabulary (a test, not a module-level
    # assert — that would couple the runner's hot import chain to this module
    # and be stripped under -O).
    from src.runner.executors import codex_cli
    assert codex_cli.TERMINAL_REASONS <= frozenset(result_capture.TERMINAL_REASONS)


class TestServedModel:
    def test_matching_model_is_ok(self):
        assert served_model_violation(capture_result_message(_msg()),
                                      "claude-sonnet-4-6", final_text="text") is None

    def test_date_suffixed_served_id_matches_requested_family(self):
        cap = capture_result_message(_msg(model_usage={"claude-opus-4-7-20260301": {}}))
        assert served_model_violation(cap, "claude-opus-4-7", final_text="text") is None

    def test_wrong_served_model_is_rejected(self):
        cap = capture_result_message(_msg(model_usage={"claude-sonnet-4-6": {}}))
        v = served_model_violation(cap, "claude-opus-5-5", final_text="text")
        assert v is not None and "claude-opus-5-5" in v

    def test_bare_alias_request_is_not_rejected(self):
        # POST /api/jobs and the dispatch MCP pass free-text model strings
        # through unvalidated; the CLI accepts family aliases and reports the
        # canonical id in modelUsage. A job that ran correctly on `sonnet`
        # must not fail as unrecognized_model.
        cap = capture_result_message(_msg(model_usage={"claude-sonnet-4-6": {}}))
        assert served_model_violation(cap, "sonnet", final_text="text") is None
        cap = capture_result_message(_msg(model_usage={"claude-opus-4-7-20260301": {}}))
        assert served_model_violation(cap, "opus-4-7", final_text="text") is None
        assert served_model_violation(cap, "sonnet", final_text="text") is not None

    def test_zero_usage_with_text_and_api_duration_is_ok(self):
        # Review Focus: short chat jobs often report all-zero usage but real text.
        cap = capture_result_message(_msg(usage=ZERO_USAGE, model_usage={}))
        assert served_model_violation(cap, "claude-sonnet-4-6",
                                      final_text="The answer is 42.") is None

    def test_missing_model_usage_with_real_usage_is_ok(self):
        # A ResultMessage without modelUsage → absent ≠ wrong.
        cap = capture_result_message(_msg(model_usage=None))
        assert served_model_violation(cap, "claude-sonnet-4-6",
                                      final_text="TASK_COMPLETE: x") is None

    def test_missing_model_usage_and_empty_everything_is_rejected(self):
        # The silent-empty-success trap (claude-anthropic.md §7): unknown id →
        # no text, zero usage, zero api time, no error flag.
        cap = capture_result_message(_msg(model_usage=None, usage=ZERO_USAGE,
                                          duration_api_ms=0, result=""))
        v = served_model_violation(cap, "claude-opus-5-5", final_text="")
        assert v is not None and "empty" in v

    def test_present_model_usage_but_no_api_time_and_no_usage_is_rejected(self):
        cap = capture_result_message(_msg(usage=ZERO_USAGE, duration_api_ms=0))
        assert served_model_violation(cap, "claude-sonnet-4-6", final_text="") is not None

    def test_final_text_is_keyword_only(self):
        sig = inspect.signature(served_model_violation)
        assert sig.parameters["final_text"].kind is inspect.Parameter.KEYWORD_ONLY


class TestColumnsAndHelpers:
    def test_result_columns_shape(self):
        # cost_usd_list is passed IN (the runner computes it with
        # pricing.price_usage); sdk_cost_usd is the SDK's own figure off the
        # capture. Two columns, two provenances — spec §2.8.
        cols = result_columns(capture_result_message(_msg()), terminal_reason="ok",
                              cli_version="2.1.139", cost_usd_list=Decimal("0.0975"))
        assert cols == {
            "cli_version": "2.1.139", "model_served": "claude-sonnet-4-6",
            "input_tokens": 15, "output_tokens": 9363, "cache_read_tokens": 379675,
            "cache_write_1h_tokens": 12000, "cache_write_5m_tokens": 0,
            "num_turns": 12, "duration_api_ms": 180500,
            "cost_usd_list": Decimal("0.0975"),
            "sdk_cost_usd": pytest.approx(0.0812), "terminal_reason": "ok",
        }

    def test_result_columns_token_keys_come_from_usage_columns(self):
        # The two lanes cannot drift: the Anthropic row's five token keys are
        # exactly usage_columns(capture.usage).
        cap = capture_result_message(_msg(usage=FIVE_MIN_USAGE))
        cols = result_columns(cap, terminal_reason="ok", cli_version="x", cost_usd_list=None)
        expected = usage_columns(FIVE_MIN_USAGE)
        assert {k: cols[k] for k in expected} == expected
        assert cols["cache_write_5m_tokens"] == 12000

    def test_cost_usd_list_is_never_the_sdk_figure_by_default(self):
        # The keyword has no default: a call site that forgets it is a
        # TypeError, not a silent fallback to total_cost_usd (the exact defect
        # P0 round-3 #10 found — the P0 exit was comparing the SDK figure to
        # itself).
        sig = inspect.signature(result_columns)
        assert sig.parameters["cost_usd_list"].default is inspect.Parameter.empty
        with pytest.raises(TypeError):
            result_columns(capture_result_message(_msg()), terminal_reason="ok",
                           cli_version="2.1.139")

    def test_computed_none_is_stored_as_none_not_as_the_sdk_figure(self):
        cols = result_columns(capture_result_message(_msg()), terminal_reason="ok",
                              cli_version="2.1.139", cost_usd_list=None)
        assert cols["cost_usd_list"] is None
        assert cols["sdk_cost_usd"] == pytest.approx(0.0812)

    def test_result_columns_cli_version_none_when_unknown(self):
        cols = result_columns(capture_result_message(_msg()), terminal_reason="ok",
                              cli_version="", cost_usd_list=None)
        assert cols["cli_version"] is None

    @pytest.mark.parametrize("exc,expected", [
        (asyncio.TimeoutError(), "timeout"),
        (asyncio.CancelledError(), "interrupted"),
        (RuntimeError("unrecognized_model: silent empty success — x"), "unrecognized_model"),
        (RuntimeError("API terminal error (session produced no work): API Error: 529"), "api_error"),
        (RuntimeError("workspace creation failed for a workspace-tier job: boom"), "error"),
        (RuntimeError("session error (error_during_execution): 401 unauthorized auth expired"), "auth_expired"),
        # The three enforcement categories survive a raise: _run_in_process puts
        # the category in the message text (B3), so the failure branch in
        # main._process_job records the same reason the completed path would.
        (RuntimeError("session error (error_during_execution; api_retry account_on_hold): suspended"), "account_on_hold"),
        (RuntimeError("session error (api_retry oauth_org_not_allowed): revoked"), "oauth_revoked"),
        (RuntimeError("session error (api_retry billing_error): payment required"), "billing_error"),
        (RuntimeError("session error (api_retry rate_limit): slow down"), "rate_limited"),
        (ValueError("anything else"), "error"),
        # Anchored heuristics (whole-tier review 2026-10-22): a category or an
        # auth-looking fragment inside infrastructure text is NOT the session's
        # own signal.
        (RuntimeError("workspace creation failed for x: git push rate_limit by remote"), "error"),
        (RuntimeError("git: Authentication failed for https://x; HTTP 403"), "error"),
        (RuntimeError("session error (error_during_execution): 403 forbidden, auth token revoked"), "auth_expired"),
    ])
    def test_exception_mapping(self, exc, expected):
        assert terminal_reason_for_exception(exc) == expected

    def test_quota_exhausted_maps_to_rate_limited(self):
        from src.runner.quota import QuotaExhausted
        assert terminal_reason_for_exception(QuotaExhausted(None, "x")) == "rate_limited"

    def test_exception_mapping_outputs_are_in_vocabulary(self):
        for exc in (RuntimeError("x"), asyncio.TimeoutError(), KeyError("k")):
            assert terminal_reason_for_exception(exc) in TERMINAL_REASONS

    def test_same_model_prefix_rules(self):
        assert same_model("claude-sonnet-4-6", "claude-sonnet-4-6")
        assert same_model("claude-sonnet-4-6-20260101", "claude-sonnet-4-6")
        assert same_model("CLAUDE-SONNET-4-6", "claude-sonnet-4-6")
        assert not same_model("claude-sonnet-4-6", "claude-opus-4-7")
        assert not same_model("", "claude-opus-4-7")

    def test_requested_matches_served_alias_rules(self):
        assert requested_matches_served("claude-sonnet-4-6", "sonnet")
        assert requested_matches_served("claude-opus-4-7-20260301", "opus-4-7")
        assert not requested_matches_served("claude-opus-4-7-20260301", "sonnet")
        # A full `claude-` id goes through same_model only (prefix rule),
        # never the hyphen-bounded alias search.
        assert requested_matches_served("claude-sonnet-4-6", "claude-sonnet")
        assert not requested_matches_served("claude-sonnet-4-6", "claude-opus")
        assert not requested_matches_served("claude-x-sonnet-4-6", "claude-sonnet")
        assert not requested_matches_served("", "sonnet")


class TestUsageColumns:
    def test_codex_flat_usage_maps_to_the_1h_arm(self):
        # The executor lane's usage is codex_cli.map_usage output: flat SDK key
        # names, no nested cache_creation object → the flat write count lands
        # on the 1-h arm (pricing.cache_write_buckets), 5-m is 0.
        from src.runner.executors import codex_cli
        mapped = codex_cli.map_usage({"input_tokens": 100, "cached_input_tokens": 40,
                                      "cache_write_input_tokens": 7, "output_tokens": 9,
                                      "reasoning_output_tokens": 3})
        assert usage_columns(mapped) == {
            "input_tokens": 100, "output_tokens": 9, "cache_read_tokens": 40,
            "cache_write_1h_tokens": 7, "cache_write_5m_tokens": 0,
        }

    def test_nested_buckets_win(self):
        cols = usage_columns(FIVE_MIN_USAGE)
        assert cols["cache_write_1h_tokens"] == 0
        assert cols["cache_write_5m_tokens"] == 12000
        assert usage_columns(REAL_USAGE)["cache_write_1h_tokens"] == 12000

    def test_reasoning_tokens_ignored(self):
        cols = usage_columns({"output_tokens": 9, "reasoning_output_tokens": 3})
        assert cols["output_tokens"] == 9
        assert "reasoning_output_tokens" not in cols
        assert set(cols) == {"input_tokens", "output_tokens", "cache_read_tokens",
                             "cache_write_1h_tokens", "cache_write_5m_tokens"}

    def test_empty_and_garbage_usage_are_zero_rows(self):
        zero = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
                "cache_write_1h_tokens": 0, "cache_write_5m_tokens": 0}
        assert usage_columns(None) == zero
        assert usage_columns({}) == zero
        assert usage_columns({"input_tokens": "garbage"}) == zero

    def test_usage_columns_goes_through_pricing_cache_write_buckets(self, monkeypatch):
        from src.runner import pricing
        monkeypatch.setattr(pricing, "cache_write_buckets", lambda usage: (111, 222))
        cols = usage_columns(REAL_USAGE)
        assert (cols["cache_write_1h_tokens"], cols["cache_write_5m_tokens"]) == (111, 222)


class TestUsageIsEmpty:
    def test_session_reexports_the_relocated_helper(self):
        from src.runner import session
        assert session.usage_is_empty is usage_is_empty

    def test_all_zero_and_missing_are_empty(self):
        assert usage_is_empty(None) and usage_is_empty({}) and usage_is_empty(ZERO_USAGE)
        assert usage_is_empty({"input_tokens": "x", "output_tokens": None})

    def test_any_of_the_four_counters_is_work(self):
        for key in ("input_tokens", "output_tokens",
                    "cache_read_input_tokens", "cache_creation_input_tokens"):
            assert not usage_is_empty({key: 1})
        # reasoning tokens alone are not one of the four (no column)
        assert usage_is_empty({"reasoning_output_tokens": 5})

    def test_capture_property_agrees_with_the_helper(self):
        assert capture_result_message(_msg(usage=ZERO_USAGE)).usage_empty is usage_is_empty(ZERO_USAGE)
        assert capture_result_message(_msg()).usage_empty is usage_is_empty(REAL_USAGE)


# ── B3: wiring into session.py / main.py ─────────────────────────────────────
#
# The run_session cases reuse the provider-dispatch harness (every collaborator
# of run_session faked, `h.db` capturing each UPDATE); importing the fixture
# function puts it in this module's namespace, which is how pytest finds it.

from tests.test_provider_dispatch import (  # noqa: E402,F401 (fixtures)
    _event,
    _job as _dispatch_job,
    _skill,
    harness,
    main_harness,
)


def _statement_params(h) -> list[dict]:
    return [dict(s.compile().params) for s in h.db.statements]


def _column_stamp(h) -> dict:
    """The one-site column UPDATE run_session issues after the lane branch
    (the row stamp that carries `cli_version`)."""
    stamps = [p for p in _statement_params(h) if "cli_version" in p]
    assert len(stamps) == 1, f"expected exactly one column stamp, got {stamps}"
    return stamps[0]


def _resolved_stamp(h) -> dict:
    stamps = [p for p in _statement_params(h) if "resolved_provider" in p]
    assert len(stamps) == 1
    return stamps[0]


def _anthropic_capture(**over) -> ResultCapture:
    base = dict(
        subtype="success", num_turns=2, duration_ms=4000, duration_api_ms=1500,
        total_cost_usd=0.0123, stop_reason="end_turn",
        usage={"input_tokens": 3, "output_tokens": 1, "cache_read_input_tokens": 0,
               "cache_creation_input_tokens": 0},
        model_usage={"claude-sonnet-4-6": {"inputTokens": 3}},
    )
    base.update(over)
    return ResultCapture(**base)


class TestSessionWiring:
    def test_run_in_process_signature_returns_capture(self):
        from src.runner import session
        sig = inspect.signature(session._run_in_process)
        assert str(sig.return_annotation).endswith("tuple[str, dict[str, Any], ResultCapture]")

    async def test_run_executor_returns_cli_version(self, tmp_path, monkeypatch):
        # ExecResult.cli_version used to be dropped on the floor by the
        # 3-tuple; the executor lane's `jobs.cli_version` is the Codex CLI.
        from src.registry import models as reg
        from src.runner import session
        from src.runner.executors.codex_cli import ExecResult
        from tests.test_provider_dispatch import _FakeExecutor

        sig = inspect.signature(session._run_executor)
        assert str(sig.return_annotation).endswith(
            "tuple[str, dict[str, Any], str | None, str | None]")

        fake = _FakeExecutor(ExecResult(
            final_text="done\nTASK_COMPLETE: x", usage={"input_tokens": 1, "output_tokens": 1},
            terminal_reason="ok", model_served="gpt-6-luna-2026-10", thread_id="t",
            cli_version="codex-cli 0.162.0-alpha.17.2", exit_code=0, error=None))
        monkeypatch.setattr(session, "_EXECUTORS", {"codex_cli": fake})
        monkeypatch.setattr(session, "_EXECUTOR_SLOTS", {})
        monkeypatch.setattr(session.settings, "codex_sandbox_default", "workspace-write")
        monkeypatch.setattr(session.settings, "server_root", tmp_path)
        job = _dispatch_job()
        out = await session._run_executor(
            job, reg.ModelRef("codex", "gpt-6-luna"), cwd=tmp_path,
            system_prompt="S", skill_cfg=None)
        assert len(out) == 4
        text, usage, model_served, cli_version = out
        assert text.startswith("done") and usage == {"input_tokens": 1, "output_tokens": 1}
        assert model_served == "gpt-6-luna-2026-10"
        assert cli_version == "codex-cli 0.162.0-alpha.17.2"   # raw here; normalised at the stamp

    def test_cli_version_comes_from_the_sdk_package_not_a_subprocess(self, monkeypatch):
        # Spec §2.3 row 007: "= claude_agent_sdk._cli_version.__cli_version__
        # … no subprocess or SystemMessage parse". Verified against the pinned
        # wheel: the attribute is "2.1.139".
        from claude_agent_sdk import _cli_version
        from src.runner import session
        session.cli_version.cache_clear()
        monkeypatch.setattr(_cli_version, "__cli_version__", "2.1.140", raising=False)
        assert session.cli_version() == "2.1.140"
        assert session.cli_version() == "2.1.140"        # cached
        session.cli_version.cache_clear()

    def test_cli_version_is_short_and_unknown_when_the_attribute_is_gone(self, monkeypatch):
        from claude_agent_sdk import _cli_version
        from src.runner import session
        session.cli_version.cache_clear()
        monkeypatch.delattr(_cli_version, "__cli_version__", raising=False)
        assert session.cli_version() == "unknown"
        session.cli_version.cache_clear()
        monkeypatch.setattr(_cli_version, "__cli_version__", "x" * 100, raising=False)
        assert len(session.cli_version()) <= 24         # jobs.cli_version is s24
        session.cli_version.cache_clear()

    def test_session_spawns_no_subprocess_for_the_cli_version(self):
        # The subprocess apparatus round 1 planned here is gone; a future
        # reader must not reintroduce it (spec §2.3 row 007).
        from src.runner import session
        src = inspect.getsource(session.cli_version)
        assert "subprocess" not in src and "claude --version" not in src
        assert "_cli_version" in src

    async def test_cli_version_stamped_per_lane(self, harness, monkeypatch):
        from src.runner import session
        h = harness
        # Anthropic lane: the SDK-bundled CLI's version.
        monkeypatch.setattr(session, "cli_version", lambda: "9.9.9")

        async def fake_run_in_process(job_id, prompt, options):
            return "SDK did it.", {"input_tokens": 3, "output_tokens": 1}, _anthropic_capture()
        monkeypatch.setattr(session, "_run_in_process", fake_run_in_process)
        h.skill = _skill(isolation="workspace", model="claude-opus-5")
        await session.run_session(_dispatch_job(payload={"model": "sonnet"}))
        assert _column_stamp(h)["cli_version"] == "9.9.9"
        assert _resolved_stamp(h)["resolved_provider"] == "anthropic"

        # Codex lane: the Codex CLI's version from ExecResult (the harness
        # default is the real `codex --version` line), normalised, never the SDK's.
        h.db.statements.clear()
        h.skill = _skill(isolation="workspace")
        await session.run_session(_dispatch_job())
        assert _column_stamp(h)["cli_version"] == "0.162.0-alpha.17.2"
        assert _resolved_stamp(h)["resolved_provider"] == "codex"

    async def test_terminal_reason_derived_only_on_anthropic_branch(self, harness, monkeypatch):
        from src.runner import session
        h = harness

        async def fake_run_in_process(job_id, prompt, options):
            return ("SDK did it.", {"input_tokens": 3, "output_tokens": 1},
                    _anthropic_capture(subtype="error_max_turns", stop_reason="max_turns"))
        monkeypatch.setattr(session, "_run_in_process", fake_run_in_process)
        h.skill = _skill(isolation="workspace", model="claude-opus-5")
        job = _dispatch_job(payload={"model": "sonnet"})
        result = await session.run_session(job)
        # D-P1-2: max_turns keeps `completed`; the typed reason is the column.
        assert result["terminal_reason"] == "max_turns"
        assert result["model_served"] == "claude-sonnet-4-6"
        assert _event(job.id, "job_completed")["terminal_reason"] == "max_turns"
        stamp = _column_stamp(h)
        assert stamp["terminal_reason"] == "max_turns"
        assert stamp["model_served"] == "claude-sonnet-4-6"

        # Executor lane: ExecResult.terminal_reason is the source ("ok" or
        # ExecutorFailed); derive_terminal_reason is never consulted.
        h.db.statements.clear()
        h.skill = _skill(isolation="workspace")
        job = _dispatch_job()
        result = await session.run_session(job)
        assert result["terminal_reason"] == "ok"
        assert "terminal_reason" not in _column_stamp(h)
        src = inspect.getsource(session.run_session)
        tree = ast.parse(src)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and ast.unparse(n.func).endswith("derive_terminal_reason")]
        assert len(calls) == 1
        lane_if = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                       and ast.unparse(n.test) == "options is not None")
        assert any(n is calls[0] for n in ast.walk(ast.Module(body=lane_if.body, type_ignores=[])))

    async def test_anthropic_lane_stamps_the_capture_columns(self, harness, monkeypatch):
        from src.runner import session
        h = harness

        async def fake_run_in_process(job_id, prompt, options):
            return "SDK did it.", {"input_tokens": 3, "output_tokens": 1}, _anthropic_capture()
        monkeypatch.setattr(session, "_run_in_process", fake_run_in_process)
        monkeypatch.setattr(session, "cli_version", lambda: "2.1.139")
        h.skill = _skill(isolation="workspace", model="claude-opus-5")
        job = _dispatch_job(payload={"model": "sonnet"})
        result = await session.run_session(job)

        stamp = _column_stamp(h)
        assert (stamp["input_tokens"], stamp["output_tokens"],
                stamp["cache_read_tokens"], stamp["cache_write_1h_tokens"],
                stamp["cache_write_5m_tokens"]) == (3, 1, 0, 0, 0)
        assert stamp["num_turns"] == 2 and stamp["duration_api_ms"] == 1500
        assert stamp["sdk_cost_usd"] == 0.0123
        # cost_usd_list is pricing.price_usage(model_served, usage): the ONE
        # definition, a Decimal, never the SDK figure.
        from src.runner import pricing
        expected = pricing.price_usage("claude-sonnet-4-6", {"input_tokens": 3, "output_tokens": 1})
        assert isinstance(expected, Decimal) and expected > 0
        assert stamp["cost_usd_list"] == expected
        assert stamp["terminal_reason"] == "ok" and stamp["cli_version"] == "2.1.139"

        done = _event(job.id, "job_completed")
        assert done["provider"] == "anthropic" and done["model_served"] == "claude-sonnet-4-6"
        assert done["num_turns"] == 2 and done["duration_api_ms"] == 1500
        assert done["cost_usd_list"] == float(expected) and done["sdk_cost_usd"] == 0.0123
        assert done["stop_reason"] == "end_turn"
        assert done["usage"] == {"input_tokens": 3, "output_tokens": 1}   # C14: unchanged
        # The return dict (→ jobs.result JSON) carries the two headline numbers.
        assert result["num_turns"] == 2 and result["cost_usd_list"] == float(expected)

    async def test_executor_lane_writes_token_columns(self, harness):
        from src.runner import session
        from src.runner.executors import codex_cli
        from src.runner.executors.codex_cli import ExecResult
        h = harness
        h.executor.result = ExecResult(
            final_text="Did it.\nTASK_COMPLETE: x",
            usage=codex_cli.map_usage({"input_tokens": 100, "cached_input_tokens": 40,
                                       "cache_write_input_tokens": 8, "output_tokens": 7,
                                       "reasoning_output_tokens": 3}),
            terminal_reason="ok", model_served="gpt-6-luna-2026-10",
            thread_id="thr_1", cli_version="codex-cli 0.162.0-alpha.17.2", exit_code=0, error=None)
        h.skill = _skill(isolation="workspace")
        job = _dispatch_job()
        result = await session.run_session(job)

        stamp = _column_stamp(h)
        assert (stamp["input_tokens"], stamp["output_tokens"], stamp["cache_read_tokens"],
                stamp["cache_write_1h_tokens"]) == (100, 7, 40, 8)   # flat key → the 1-h arm
        assert stamp["cache_write_5m_tokens"] == 0
        assert stamp["cli_version"] == "0.162.0-alpha.17.2"
        assert stamp["cost_usd_list"] is None            # no Codex price table in Phase 1
        for absent in ("num_turns", "duration_api_ms", "sdk_cost_usd"):
            assert stamp.get(absent) is None             # no source on that lane → NULL
        done = _event(job.id, "job_completed")
        assert done["cost_usd_list"] is None and done["num_turns"] is None
        assert done["sdk_cost_usd"] is None and done["duration_api_ms"] is None
        assert done["stop_reason"] is None
        assert result["cost_usd_list"] is None and result["num_turns"] is None

    def test_three_quota_raises_keep_their_source(self):
        from src.runner import session
        src = inspect.getsource(session._run_in_process)
        raises = [ast.unparse(n) for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.Raise) and "QuotaExhausted" in ast.unparse(n)]
        assert len(raises) == 3, raises
        assert all("source=" in r for r in raises)
        assert sum(("'vendor'" in r or '"vendor"' in r) for r in raises) == 1

    def test_api_retry_is_collected_before_the_rate_limit_branch(self):
        # The enforcement category must be recorded even on the paths that
        # `continue` or raise before a ResultMessage (spec §2.4 / P0 #M16).
        from src.runner import session
        src = inspect.getsource(session._run_in_process)
        body = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.AsyncFor)).body
        tests_ = [ast.unparse(n.test) for n in body if isinstance(n, ast.If)]
        sys_idx = next(i for i, t in enumerate(tests_) if "SystemMessage" in t and "api_retry" in t)
        rl_idx = next(i for i, t in enumerate(tests_) if "RateLimitEvent" in t)
        assert sys_idx < rl_idx
        assert '"api_retry"' in src and "capture_result_message(" in src
        assert "served_model_violation(" in src and '"job_result_rejected"' in src
        assert "is_api_terminal_session(" in src          # the banner belt stays

    async def test_enforcement_category_fails_the_session(self, monkeypatch, fake_redis):
        # A system/api_retry with an enforcement category → the session fails
        # with the category in the text (terminal_reason_for_exception maps it)
        # instead of recording a silent success; `api_retry` is audited
        # without message text. Driven through a fake SDK client.
        from claude_agent_sdk import ResultMessage, SystemMessage
        from src import audit_log
        from src.runner import session

        msgs = [
            SystemMessage(subtype="api_retry",
                          data={"error": "account_on_hold", "attempt": 2,
                                "message": "SECRET-ish text that must not be logged"}),
            ResultMessage(subtype="success", duration_ms=10, duration_api_ms=0,
                          is_error=False, num_turns=0, session_id="s",
                          usage={"input_tokens": 0, "output_tokens": 0}, result=""),
        ]

        class FakeClient:
            def __init__(self, options=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def query(self, prompt):
                pass

            async def receive_response(self):
                for m in msgs:
                    yield m

        monkeypatch.setattr(session, "ClaudeSDKClient", FakeClient)
        monkeypatch.setattr(session, "redis", fake_redis)   # _publish_stream, never the real client
        job_id = "b3-enforce-" + "1" * 8
        with pytest.raises(RuntimeError) as ei:
            await session._run_in_process(job_id, "p", SimpleNamespace(model="claude-sonnet-4-6"))
        assert "account_on_hold" in str(ei.value)
        assert terminal_reason_for_exception(ei.value) == "account_on_hold"
        events = audit_log.read(job_id)
        retry = [e for e in events if e["kind"] == "api_retry"]
        assert retry and retry[0]["error"] == "account_on_hold" and retry[0]["attempt"] == 2
        assert all("SECRET" not in str(e) for e in events)   # category + attempt only

    async def test_silent_empty_success_is_rejected_with_audit(self, monkeypatch, fake_redis):
        from claude_agent_sdk import ResultMessage
        from src import audit_log
        from src.runner import session

        msgs = [ResultMessage(subtype="success", duration_ms=10, duration_api_ms=0,
                              is_error=False, num_turns=0, session_id="s",
                              usage={"input_tokens": 0, "output_tokens": 0}, result="")]

        class FakeClient:
            def __init__(self, options=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def query(self, prompt):
                pass

            async def receive_response(self):
                for m in msgs:
                    yield m

        monkeypatch.setattr(session, "ClaudeSDKClient", FakeClient)
        monkeypatch.setattr(session, "redis", fake_redis)   # _publish_stream, never the real client
        job_id = "b3-silent-" + "2" * 8
        with pytest.raises(RuntimeError) as ei:
            await session._run_in_process(job_id, "p", SimpleNamespace(model="claude-opus-5-5"))
        assert str(ei.value).startswith("unrecognized_model")
        assert terminal_reason_for_exception(ei.value) == "unrecognized_model"
        rej = [e for e in audit_log.read(job_id) if e["kind"] == "job_result_rejected"]
        assert rej and rej[0]["reason"] == "unrecognized_model"
        assert rej[0]["requested_model"] == "claude-opus-5-5" and rej[0]["detail"]

    async def test_a_real_result_message_returns_the_capture(self, monkeypatch, fake_redis):
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
        from src.runner import session

        msgs = [
            AssistantMessage(content=[TextBlock(text="pong")], model="claude-sonnet-4-6"),
            ResultMessage(subtype="success", duration_ms=900, duration_api_ms=700,
                          is_error=False, num_turns=1, session_id="s", total_cost_usd=0.002,
                          usage={"input_tokens": 12, "output_tokens": 2,
                                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                          result="pong", stop_reason="end_turn",
                          model_usage={"claude-sonnet-4-6-20260301": {}}),
        ]

        class FakeClient:
            def __init__(self, options=None):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def query(self, prompt):
                pass

            async def receive_response(self):
                for m in msgs:
                    yield m

        monkeypatch.setattr(session, "ClaudeSDKClient", FakeClient)
        monkeypatch.setattr(session, "redis", fake_redis)   # _publish_stream, never the real client
        text, usage, capture = await session._run_in_process(
            "b3-ok-" + "3" * 8, "p", SimpleNamespace(model="claude-sonnet-4-6"))
        assert text == "pong" and usage["input_tokens"] == 12
        assert isinstance(capture, ResultCapture)
        assert capture.num_turns == 1 and capture.duration_api_ms == 700
        assert capture.model_served == "claude-sonnet-4-6-20260301"
        assert derive_terminal_reason(capture) == "ok"


class TestMainWiring:
    def test_terminal_values_write_token_and_cost_columns(self):
        from src.models import JobStatus
        from src.runner import main as runner_main

        base = runner_main._terminal_values(JobStatus.completed, result={"summary": "s"}, error=None)
        for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_1h_tokens",
                  "cache_write_5m_tokens", "num_turns", "cost_usd_list"):
            assert k not in base                           # unknown → left to the session's stamp

        full = runner_main._terminal_values(
            JobStatus.completed, result={"summary": "s"}, error=None,
            usage={"input_tokens": 5, "output_tokens": 2, "cache_read_input_tokens": 1,
                   "cache_creation_input_tokens": 4},
            num_turns=3, cost_usd_list=3.485)
        assert (full["input_tokens"], full["output_tokens"], full["cache_read_tokens"],
                full["cache_write_1h_tokens"], full["cache_write_5m_tokens"]) == (5, 2, 1, 4, 0)
        assert full["num_turns"] == 3
        assert full["cost_usd_list"] == Decimal("3.485")    # numeric(10,4) wants a Decimal
        assert isinstance(full["cost_usd_list"], Decimal)
        # And the completed path hands exactly these through from the result dict.
        src = ast.unparse(next(
            n for n in ast.walk(ast.parse((Path(__file__).resolve().parents[1]
                                           / "src" / "runner" / "main.py").read_text()))
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job"))
        for key in ("usage", "num_turns", "cost_usd_list"):
            assert f"{key}=result.get('{key}')" in src or f'{key}=result.get("{key}")' in src

    async def test_generic_anthropic_failure_maps_exception(self, main_harness):
        from src.models import JobStatus
        from src.runner import main as runner_main

        h = main_harness(RuntimeError("unrecognized_model: silent empty success — empty result"),
                         "anthropic")
        await runner_main._process_job(h.job.id)
        fin = h.finished[0]
        assert fin["status"] is JobStatus.failed
        assert fin["terminal_reason"] == "unrecognized_model"
        failed = _event(h.job.id, "job_failed")
        assert failed["terminal_reason"] == "unrecognized_model"
        assert len(h.escalated) == 1                      # a known-good model engages

        h = main_harness(RuntimeError("session error (error; api_retry billing_error): no output"),
                         "anthropic")
        await runner_main._process_job(h.job.id)
        assert h.finished[0]["terminal_reason"] == "billing_error"
        assert _event(h.job.id, "job_failed")["terminal_reason"] == "billing_error"

    def test_generic_branch_has_no_interim_literal(self):
        # A2's interim `terminal_reason="api_error"` in the generic handler is
        # replaced by the mapping; the typed handlers above it keep theirs.
        main_py = Path(__file__).resolve().parents[1] / "src" / "runner" / "main.py"
        tree = ast.parse(main_py.read_text())
        process_job = next(n for n in ast.walk(tree)
                           if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job")
        generic = [n for n in ast.walk(process_job)
                   if isinstance(n, ast.ExceptHandler) and isinstance(n.type, ast.Name)
                   and n.type.id == "Exception" and n.name == "exc"]
        assert len(generic) == 1
        src = ast.unparse(generic[0])
        assert "terminal_reason_for_exception(exc)" in src
        assert "terminal_reason='api_error'" not in src and 'terminal_reason="api_error"' not in src


class TestDominantModel:
    """`model_served` must name the model that did the work, not whichever
    `model_usage` key happens to come first (prod, 2026-10-22..28: the CLI's
    own haiku call was first on 39 of 111 jobs, so Opus sessions were stamped
    — and priced — as Haiku)."""

    def test_model_served_is_the_dominant_model_not_the_first_key(self):
        from src.runner.result_capture import dominant_model
        usage = {                                   # the real prod shape
            "claude-haiku-4-5-20251001": {"inputTokens": 12, "outputTokens": 31},
            "claude-opus-5": {"inputTokens": 40, "cacheReadInputTokens": 2_180_898,
                              "cacheCreationInputTokens": 52_000, "outputTokens": 12_400},
        }
        assert dominant_model(usage) == "claude-opus-5"
        assert capture_result_message(_msg(model_usage=usage)).model_served == "claude-opus-5"

    def test_snake_case_counters_count_too(self):
        from src.runner.result_capture import dominant_model
        assert dominant_model({
            "claude-haiku-4-5-20251001": {"input_tokens": 9, "output_tokens": 4},
            "claude-sonnet-4-6": {"input_tokens": 8, "cache_read_input_tokens": 500_000},
        }) == "claude-sonnet-4-6"

    def test_cost_and_context_fields_never_decide_it(self):
        from src.runner.result_capture import dominant_model
        assert dominant_model({
            "claude-haiku-4-5-20251001": {"costUSD": 99.0, "contextWindow": 200_000,
                                          "inputTokens": 5},
            "claude-opus-4-7": {"costUSD": 0.01, "inputTokens": 4_000},
        }) == "claude-opus-4-7"

    def test_countless_shapes_keep_the_first_key(self):
        # Pins the pre-fix behaviour the older cases rely on.
        from src.runner.result_capture import dominant_model
        assert dominant_model({"claude-sonnet-4-6": {}}) == "claude-sonnet-4-6"
        assert dominant_model({"claude-opus-4-7": None, "claude-sonnet-4-6": {}}) \
            == "claude-opus-4-7"
        assert dominant_model({}) is None and dominant_model(None) is None

    def test_a_haiku_dominated_session_still_reports_haiku(self):
        # Not a blanket "never haiku" rule: a session that really ran on the
        # utility model must still report it.
        from src.runner.result_capture import dominant_model
        assert dominant_model({
            "claude-haiku-4-5-20251001": {"inputTokens": 10, "cacheReadInputTokens": 90_000},
            "claude-opus-5": {"inputTokens": 3},
        }) == "claude-haiku-4-5-20251001"


# ── B3 follow-up (2026-10-28): the Codex CLI's version string overflowed
# `jobs.cli_version` (varchar(24)) on the first real Codex job after the
# Phase-1 deploy — `codex-cli 0.162.0-alpha.17.2` is 28 chars — so the
# post-session column stamp raised StringDataRightTruncationError and a job
# whose work was DONE (tokens captured, empty diff) was recorded `failed`.
# Two belts: the value is normalised to fit, and a failing stamp is audited
# instead of failing the finished job (the terminal transition re-stamps the
# token/cost subset from the result dict anyway).


class TestCliVersionColumn:
    def test_the_tool_name_prefix_is_dropped(self):
        # The Anthropic lane stamps a bare `2.1.139`; the Codex lane should
        # stamp a bare version too, not `codex --version`'s whole first line.
        from src.runner.result_capture import cli_version_column
        assert cli_version_column("codex-cli 0.162.0-alpha.17.2") == "0.162.0-alpha.17.2"

    def test_a_bare_version_is_unchanged(self):
        from src.runner.result_capture import cli_version_column
        assert cli_version_column("2.1.139") == "2.1.139"
        assert cli_version_column("  0.162.0 \n") == "0.162.0"

    def test_a_trailing_annotation_does_not_win(self):
        # `codex-cli 0.170.0 (abc123)` must stamp `0.170.0`, not `(abc123)`.
        from src.runner.result_capture import cli_version_column
        assert cli_version_column("codex-cli 0.170.0 (abc123)") == "0.170.0"
        assert cli_version_column("codex-cli 0.170.0 [stable]") == "0.170.0"
        assert cli_version_column("unknown") == "unknown"        # no version-shaped token

    def test_empty_is_none(self):
        from src.runner.result_capture import cli_version_column
        assert cli_version_column(None) is None
        assert cli_version_column("") is None
        assert cli_version_column("   ") is None

    def test_an_overlong_value_is_clipped_to_the_column(self):
        from src.runner.result_capture import CLI_VERSION_MAX, cli_version_column
        long = "0.162.0-alpha.17.2+build.20261028.9"
        assert len(long) > CLI_VERSION_MAX
        out = cli_version_column(long)
        assert out == long[:CLI_VERSION_MAX] and len(out) == CLI_VERSION_MAX

    def test_the_cap_is_the_orm_column_width(self):
        # If the column is ever widened, the cap must follow (and vice versa).
        from src.models import Job
        from src.runner.result_capture import CLI_VERSION_MAX
        assert Job.__table__.c.cli_version.type.length == CLI_VERSION_MAX

    def test_result_columns_normalises_it(self):
        cols = result_columns(_anthropic_capture(), terminal_reason="ok", cost_usd_list=None,
                              cli_version="codex-cli 0.162.0-alpha.17.2")
        assert cols["cli_version"] == "0.162.0-alpha.17.2"


class TestStampAfterTheWork:
    async def test_executor_lane_cli_version_fits_the_column(self, harness):
        from src.runner import session
        from src.runner.executors.codex_cli import ExecResult
        h = harness
        h.executor.result = ExecResult(
            final_text="Did it.\nTASK_COMPLETE: x",
            usage={"input_tokens": 38799, "output_tokens": 206, "cache_read_input_tokens": 16000},
            terminal_reason="ok", model_served="gpt-6-luna", thread_id="t",
            cli_version="codex-cli 0.162.0-alpha.17.2",   # prod 2026-10-28, job 0e09233d
            exit_code=0, error=None)
        h.skill = _skill(isolation="workspace")
        await session.run_session(_dispatch_job())
        stamp = _column_stamp(h)
        assert stamp["cli_version"] == "0.162.0-alpha.17.2"
        assert len(stamp["cli_version"]) <= result_capture.CLI_VERSION_MAX

    async def test_a_failing_column_stamp_does_not_fail_the_finished_job(self, harness):
        from src.runner import session
        h = harness
        real_execute = h.db.execute

        async def execute(stmt):
            params = dict(stmt.compile().params)
            if "cli_version" in params:
                raise RuntimeError("value too long for type character varying(24)")
            await real_execute(stmt)
        h.db.execute = execute

        h.skill = _skill(isolation="workspace")
        job = _dispatch_job()
        result = await session.run_session(job)           # must not raise

        # The job's work is intact: result dict, summary, job_completed.
        assert result["usage"] == {"input_tokens": 10, "output_tokens": 5}
        assert result["terminal_reason"] == "ok"
        done = _event(job.id, "job_completed")
        assert done["usage"] == {"input_tokens": 10, "output_tokens": 5}
        # …and the stamp failure is on the record, with the error, not swallowed.
        failed = _event(job.id, "result_stamp_failed")
        assert "varying(24)" in failed["error"]
        kinds = _kinds(job.id)
        assert kinds.index("result_stamp_failed") < kinds.index("job_completed")
        # The resolved_* stamp still landed; the column stamp was the one refused.
        assert len(h.db.statements) == 1 and "resolved_provider" in _statement_params(h)[0]

    def test_audit_log_docstring_lists_result_stamp_failed(self):
        doc = (Path(__file__).resolve().parents[1] / "src" / "audit_log.py").read_text()
        assert "- result_stamp_failed:" in doc


def _kinds(job_id) -> list[str]:
    from src import audit_log
    return [e["kind"] for e in audit_log.read(str(job_id))]
