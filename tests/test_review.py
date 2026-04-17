"""Tests for src/runner/review.py — pure-function tests only (no SDK)."""

import tempfile
from pathlib import Path

from src.runner.review import ReviewOutcome, _parse_outcome, get_git_diff


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
