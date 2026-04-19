"""Unit tests for src/runner/proposals.py pure functions."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from src.models import ProposalChangeType, ProposalOutcome
from src.runner.proposals import (
    extract_proposal_id,
    format_proposal_line,
    is_valid_change_type,
    is_valid_outcome,
)


class TestExtractProposalId:
    def test_empty_input(self):
        assert extract_proposal_id("") is None

    def test_whitespace_only(self):
        assert extract_proposal_id("   ") is None

    def test_canonical_marker(self):
        pid = uuid.uuid4()
        assert extract_proposal_id(f"Proposal-ID: {pid}\n\nThis PR reduces max_turns.") == pid

    def test_marker_in_middle_of_pr_body(self):
        pid = uuid.uuid4()
        text = f"# Summary\n\nChange X\n\nProposal-ID: {pid}\n\ncc @reviewer"
        assert extract_proposal_id(text) == pid

    def test_no_dash_uuid(self):
        pid = uuid.uuid4()
        assert extract_proposal_id(f"Proposal-ID: {pid.hex}") == pid

    def test_underscore_variant(self):
        pid = uuid.uuid4()
        assert extract_proposal_id(f"proposal_id = {pid}") == pid

    def test_space_variant(self):
        pid = uuid.uuid4()
        assert extract_proposal_id(f"Proposal ID: {pid}") == pid

    def test_lowercase_key(self):
        pid = uuid.uuid4()
        assert extract_proposal_id(f"proposal-id: {pid}") == pid

    def test_uppercase_hex(self):
        pid = uuid.uuid4()
        assert extract_proposal_id(f"Proposal-ID: {str(pid).upper()}") == pid

    def test_no_marker(self):
        assert extract_proposal_id("Just a regular PR body") is None

    def test_malformed_hex(self):
        assert extract_proposal_id("Proposal-ID: not-a-uuid") is None

    def test_short_hex(self):
        assert extract_proposal_id("Proposal-ID: abc-def") is None

    def test_multiple_markers_returns_first(self):
        p1 = uuid.uuid4()
        p2 = uuid.uuid4()
        assert extract_proposal_id(f"Proposal-ID: {p1}\n...\nProposal-ID: {p2}") == p1


class TestIsValidChangeType:
    def test_all_canonical_values_valid(self):
        for ct in ProposalChangeType:
            assert is_valid_change_type(ct.value) is True

    def test_garbage_invalid(self):
        assert is_valid_change_type("random") is False
        assert is_valid_change_type("") is False
        assert is_valid_change_type("DEFAULT-MODEL") is False

    def test_valid_explicit_values(self):
        assert is_valid_change_type("default-model") is True
        assert is_valid_change_type("context-files") is True
        assert is_valid_change_type("frontmatter-tweak") is True
        assert is_valid_change_type("doc-update") is True


class TestIsValidOutcome:
    def test_all_canonical_values_valid(self):
        for oc in ProposalOutcome:
            assert is_valid_outcome(oc.value) is True

    def test_garbage_invalid(self):
        assert is_valid_outcome("maybe") is False
        assert is_valid_outcome("") is False
        assert is_valid_outcome("MERGED") is False


class TestProposalOutcomeIsTerminal:
    def test_pending_not_terminal(self):
        assert ProposalOutcome.pending.is_terminal is False

    def test_merged_terminal(self):
        assert ProposalOutcome.merged.is_terminal is True

    def test_rejected_terminal(self):
        assert ProposalOutcome.rejected.is_terminal is True

    def test_superseded_terminal(self):
        assert ProposalOutcome.superseded.is_terminal is True


class TestFormatProposalLine:
    def _fixed_now(self):
        return datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)

    def test_days_age(self):
        pid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        line = format_proposal_line(
            pid, "skills/x/SKILL.md", "frontmatter-tweak", "pending",
            self._fixed_now() - timedelta(days=5), now=self._fixed_now(),
        )
        assert line.startswith("12345678 ")
        assert "5d" in line
        assert "pending" in line
        assert "frontmatter-tweak" in line
        assert "skills/x/SKILL.md" in line

    def test_hours_age(self):
        pid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        line = format_proposal_line(
            pid, "f.md", "default-model", "merged",
            self._fixed_now() - timedelta(hours=3), now=self._fixed_now(),
        )
        assert "3h" in line and "merged" in line

    def test_minutes_age(self):
        pid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        line = format_proposal_line(
            pid, "f.md", "doc-update", "pending",
            self._fixed_now() - timedelta(minutes=45), now=self._fixed_now(),
        )
        assert "45m" in line

    def test_long_target_file_truncated(self):
        pid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        long_path = "projects/market-tracker/src/very/deep/nested/path/to/some/specific/file.py"
        line = format_proposal_line(
            pid, long_path, "doc-update", "pending",
            self._fixed_now() - timedelta(hours=1), now=self._fixed_now(),
        )
        assert "..." in line and "file.py" in line

    def test_short_path_not_truncated(self):
        pid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        line = format_proposal_line(
            pid, "CLAUDE.md", "doc-update", "pending",
            self._fixed_now() - timedelta(hours=1), now=self._fixed_now(),
        )
        assert "CLAUDE.md" in line and "..." not in line

    def test_naive_proposed_at_gets_utc(self):
        pid = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        line = format_proposal_line(
            pid, "f.md", "doc-update", "pending",
            datetime(2026, 4, 18, 9, 0, 0),  # naive
            now=datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert "3h" in line

    def test_id_truncated_to_8_chars(self):
        pid = uuid.UUID("abcd1234-5678-90ef-1234-567890abcdef")
        line = format_proposal_line(
            pid, "f.md", "doc-update", "pending",
            self._fixed_now() - timedelta(minutes=10), now=self._fixed_now(),
        )
        assert line.startswith("abcd1234 ")
        assert str(pid) not in line
