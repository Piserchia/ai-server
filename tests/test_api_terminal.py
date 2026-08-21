"""
Regression tests for API-terminal session detection.

Job 143c8cfb (atlas-evaluate, 2026-08-17 13:48Z) ran for 200s, produced
zero output, and its result summary was literally
"API Error: 529 Overloaded. This is a server-side issue, usually
temporary — try again in a moment. If it persists, check
status.claude.com." — yet the runner recorded status="completed".
Because the job did not fail, escalation.on_failure never fired, no
self-diagnose was enqueued, and the atlas governor was silently dark
for 10 days.

The classifier (`session.is_api_terminal_session`) plus the raise in
`_run_in_process` reclassify this shape as a failure so the existing
escalation/self-diagnose paths engage. These tests pin the classifier
so a future refactor can't accidentally re-open the hole.

Run: pipenv run pytest tests/test_api_terminal.py -v
"""

from __future__ import annotations

import pytest

from src.runner.session import (
    is_api_terminal_session,
    is_api_terminal_summary,
    usage_is_empty,
)


# The verbatim summary and usage dict from job 143c8cfb's audit log.
# volumes/audit_log/143c8cfb-bdef-4b85-83f7-c5306584a7d3.jsonl lines 3-4.
JOB_143C8CFB_SUMMARY = (
    "API Error: 529 Overloaded. This is a server-side issue, usually "
    "temporary — try again in a moment. If it persists, check "
    "status.claude.com."
)
JOB_143C8CFB_USAGE = {
    "input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "output_tokens": 0,
    "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
    "service_tier": "standard",
    "cache_creation": {
        "ephemeral_1h_input_tokens": 0,
        "ephemeral_5m_input_tokens": 0,
    },
    "inference_geo": "",
    "iterations": [],
    "speed": "standard",
}


# ── Summary banner classifier ────────────────────────────────────────────


class TestIsApiTerminalSummary:
    def test_job_143c8cfb_verbatim_banner(self):
        """The exact string from the flag case must classify as API-terminal."""
        assert is_api_terminal_summary(JOB_143C8CFB_SUMMARY)

    @pytest.mark.parametrize("banner", [
        "API Error: 500 Internal Server Error. Retry shortly.",
        "API Error: 502 Bad Gateway",
        "API Error: 503 Service Unavailable — check status.claude.com",
        "API Error: 529 Overloaded",
        "API Error: Overloaded",
        "API Error: Request timed out after 60s.",
        "API Error: overloaded_error",
        "Error: overloaded_error — try again later.",
        "Error: internal_server_error",
        "Error: api_error",
        # Case-insensitive:
        "api error: 529 overloaded",
        "ERROR: OVERLOADED_ERROR",
        # Leading whitespace tolerated:
        "   API Error: 529 Overloaded",
    ])
    def test_terminal_banner_shapes_match(self, banner):
        assert is_api_terminal_summary(banner)

    def test_400_client_error_does_not_match(self):
        # 4xx = our bug, not an API-side terminal shape. Escalation applies
        # via the normal exception path (a 4xx from Anthropic means we sent
        # something bad); the runner shouldn't magic-classify 4xx as
        # transient API failure.
        assert not is_api_terminal_summary("API Error: 400 Bad Request")

    def test_401_auth_error_does_not_match(self):
        assert not is_api_terminal_summary("API Error: 401 Unauthorized")

    def test_legit_summary_mentioning_api_error_does_not_match(self):
        # A self-diagnose or postmortem write-up may include the phrase.
        # Must NOT be classified as API-terminal.
        summary = (
            "Investigated the atlas-evaluate crash and fixed a bug in the "
            "governor. The prior API error (529) that started this incident "
            "is now handled by the runner classifier. Tests green, "
            "pushed to main."
        )
        assert not is_api_terminal_summary(summary)

    def test_summary_starting_with_api_error_but_long_does_not_match(self):
        # Real skill reports can lead with an API-error mention (e.g. a
        # postmortem). The length cap keeps the classifier conservative.
        summary = "API Error: 529 Overloaded triggered the incident. " + ("x" * 900)
        assert not is_api_terminal_summary(summary)

    @pytest.mark.parametrize("val", ["", "   \n\n", None])
    def test_empty_summary(self, val):
        assert not is_api_terminal_summary(val)

    def test_task_complete_marker_does_not_match(self):
        assert not is_api_terminal_summary("TASK_COMPLETE: fixed the bug")

    def test_generic_error_prefix_does_not_match(self):
        # "Error: FileNotFound" is NOT an API-terminal SDK error type.
        assert not is_api_terminal_summary("Error: FileNotFoundError")


# ── Usage dict classifier ────────────────────────────────────────────────


class TestUsageIsEmpty:
    def test_job_143c8cfb_usage_all_zero(self):
        assert usage_is_empty(JOB_143C8CFB_USAGE)

    @pytest.mark.parametrize("val", [None, {}])
    def test_missing_usage(self, val):
        assert usage_is_empty(val)

    @pytest.mark.parametrize("key", [
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ])
    def test_any_positive_token_makes_nonempty(self, key):
        assert not usage_is_empty({key: 1})

    def test_realistic_used_dict_not_empty(self):
        usage = {
            "input_tokens": 1234,
            "output_tokens": 567,
            "cache_read_input_tokens": 890,
            "cache_creation_input_tokens": 0,
        }
        assert not usage_is_empty(usage)

    def test_non_int_values_treated_as_zero(self):
        # SDK versions vary; garbage-shaped fields should not blow up.
        assert usage_is_empty({
            "input_tokens": None,
            "output_tokens": "abc",
            "cache_read_input_tokens": [],
        })


# ── Combined session predicate ───────────────────────────────────────────


class TestIsApiTerminalSession:
    def test_job_143c8cfb_full_shape_classified(self):
        """The verbatim (summary, usage) pair from the 2026-08-17 flag case
        must classify as API-terminal — this is the regression the fix
        exists to prevent from recurring."""
        assert is_api_terminal_session(JOB_143C8CFB_SUMMARY, JOB_143C8CFB_USAGE)

    def test_banner_but_real_usage_not_classified(self):
        # If tokens WERE consumed, the session actually did work before the
        # banner appeared. That's an ambiguous shape we deliberately do NOT
        # fail — sticking to the conservative "clear API-terminal only" rule.
        assert not is_api_terminal_session(
            JOB_143C8CFB_SUMMARY,
            {"input_tokens": 100, "output_tokens": 20},
        )

    def test_real_summary_zero_usage_not_classified(self):
        # A summary that isn't the banner shape must never be classified,
        # even if usage happens to be empty (garbage-in shouldn't over-trip).
        assert not is_api_terminal_session("TASK_COMPLETE: done", {})

    def test_empty_inputs_not_classified(self):
        assert not is_api_terminal_session("", {})
        assert not is_api_terminal_session(None, None)

    def test_long_summary_not_classified_even_with_empty_usage(self):
        summary = "API Error: 529 Overloaded triggered the incident. " + ("x" * 900)
        assert not is_api_terminal_session(summary, {})
