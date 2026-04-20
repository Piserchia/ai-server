"""Unit tests for module knowledge injection helpers in session.py."""

from __future__ import annotations

from src.runner.session import parse_skill_file_entries


SAMPLE_GOTCHAS = """\
# Gotchas

> Template header text...

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->

## 2026-04-20 — SQLAlchemy update name collision

Some body text here.

## 2026-04-20 — Never edit existing migrations

More body text.
"""

SAMPLE_EMPTY = """\
# Gotchas

> Template header text...

<!-- APPEND_ENTRIES_BELOW -->
"""

SAMPLE_NO_MARKER = """\
# Gotchas

## Some heading before the marker

This should not be parsed.
"""


class TestParseSkillFileEntries:
    def test_entries_extracted(self):
        titles = parse_skill_file_entries(SAMPLE_GOTCHAS)
        assert titles == [
            "SQLAlchemy update name collision",
            "Never edit existing migrations",
        ]

    def test_empty_file(self):
        assert parse_skill_file_entries(SAMPLE_EMPTY) == []

    def test_no_marker(self):
        # Entries before the marker are not parsed
        assert parse_skill_file_entries(SAMPLE_NO_MARKER) == []

    def test_completely_empty(self):
        assert parse_skill_file_entries("") == []

    def test_entry_without_date_prefix(self):
        text = "<!-- APPEND_ENTRIES_BELOW -->\n\n## Plain title without date\n\nbody"
        titles = parse_skill_file_entries(text)
        assert titles == ["Plain title without date"]

    def test_multiple_dashes_in_title(self):
        text = "<!-- APPEND_ENTRIES_BELOW -->\n\n## 2026-04-20 — A — B — C\n"
        titles = parse_skill_file_entries(text)
        assert titles == ["A — B — C"]
