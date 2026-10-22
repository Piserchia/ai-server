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
