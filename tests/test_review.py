"""Tests for src/runner/review.py — pure-function tests only (no SDK)."""

import tempfile
from pathlib import Path

from src.runner.review import (
    ReviewOutcome,
    _parse_outcome,
    format_structured_review,
    get_git_diff,
    head_commit_epoch,
    is_stale_head,
    outcome_from_structured,
)


class TestOutcomeFromStructured:
    """Structured-output verdict path (SDK output_format, 2026-07-27)."""

    def test_verdicts_map(self):
        assert outcome_from_structured({"verdict": "LGTM", "review": "r"}) == ReviewOutcome.lgtm
        assert outcome_from_structured({"verdict": "BLOCKER"}) == ReviewOutcome.blocker
        assert outcome_from_structured({"verdict": "CHANGES"}) == ReviewOutcome.changes_requested

    def test_case_insensitive(self):
        assert outcome_from_structured({"verdict": "lgtm"}) == ReviewOutcome.lgtm

    def test_unusable_returns_none_for_text_fallback(self):
        assert outcome_from_structured(None) is None
        assert outcome_from_structured("LGTM") is None
        assert outcome_from_structured({"verdict": "MAYBE"}) is None
        assert outcome_from_structured({}) is None

    def test_format_renders_sections(self):
        text = format_structured_review(
            {"verdict": "CHANGES", "review": "fix x", "approach": "read first"})
        assert text.startswith("CHANGES")
        assert "Review: fix x" in text and "Approach: read first" in text


class TestParseOutcome:
    def test_lgtm_simple(self):
        assert _parse_outcome("LGTM\nLooks good.") == ReviewOutcome.lgtm

    def test_lgtm_with_details(self):
        assert _parse_outcome("LGTM - no issues found\n\nClean code.") == ReviewOutcome.lgtm

    def test_lgtm_lowercase(self):
        assert _parse_outcome("lgtm\nall good") == ReviewOutcome.lgtm

    def test_blocker_simple(self):
        assert _parse_outcome("BLOCKER\nHardcoded API key on line 42.") == ReviewOutcome.blocker

    def test_blocker_lowercase(self):
        assert _parse_outcome("blocker\nsecurity issue") == ReviewOutcome.blocker

    def test_changes_simple(self):
        assert _parse_outcome("CHANGES\nMinor style issues.") == ReviewOutcome.changes_requested

    def test_changes_lowercase(self):
        assert _parse_outcome("changes\nshould fix naming") == ReviewOutcome.changes_requested

    def test_unknown_text_defaults_to_changes(self):
        assert _parse_outcome("This looks mostly fine but...") == ReviewOutcome.changes_requested

    def test_empty_string_defaults_to_changes(self):
        assert _parse_outcome("") == ReviewOutcome.changes_requested

    def test_none_defaults_to_changes(self):
        # Should not crash
        assert _parse_outcome(None) == ReviewOutcome.changes_requested

    def test_whitespace_only_defaults_to_changes(self):
        assert _parse_outcome("   \n  \n  ") == ReviewOutcome.changes_requested

    def test_multiline_with_leading_whitespace(self):
        assert _parse_outcome("  LGTM  \nEverything checks out.") == ReviewOutcome.lgtm

    def test_blocker_with_extra_words_on_line(self):
        assert _parse_outcome("BLOCKER — critical security issue") == ReviewOutcome.blocker

    def test_lgtm_with_emoji(self):
        # Reviewers might add emoji
        assert _parse_outcome("LGTM 👍\nNo issues.") == ReviewOutcome.lgtm


class TestGetGitDiff:
    def test_non_git_directory_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            assert get_git_diff(Path(d)) == ""

    def test_nonexistent_directory_returns_empty(self):
        assert get_git_diff(Path("/nonexistent/path/abc123")) == ""


class TestStaleHeadGuard:
    """Wrong-diff guard (INV-13, 2026-08-05): post-review must not grade a
    checkout whose HEAD predates the job — that diff is someone else's."""

    def test_head_older_than_job_start_is_stale(self):
        assert is_stale_head(head_epoch=1_000_000, job_started_epoch=1_000_000 + 3600)

    def test_head_newer_than_job_start_is_fresh(self):
        assert not is_stale_head(head_epoch=1_000_000 + 60, job_started_epoch=1_000_000)

    def test_slack_absorbs_clock_wobble(self):
        # HEAD 60s before job start is inside the 120s slack — not stale.
        assert not is_stale_head(head_epoch=1_000_000 - 60, job_started_epoch=1_000_000)
        # Just past the slack boundary → stale.
        assert is_stale_head(head_epoch=1_000_000 - 121, job_started_epoch=1_000_000)

    def test_unknown_epochs_fail_open(self):
        # Unknown HEAD or start → not stale; the empty-diff check still guards.
        assert not is_stale_head(None, 1_000_000)
        assert not is_stale_head(1_000_000, None)
        assert not is_stale_head(None, None)

    def test_head_commit_epoch_non_repo_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert head_commit_epoch(Path(tmp)) is None

