"""Unit tests for stale-context warning helpers in src/runner/retrospective.py."""

from __future__ import annotations

import os
import time
from pathlib import Path

from src.runner.retrospective import _days_since, _newest_mtime


class TestNewestMtime:
    def test_empty_directory(self, tmp_path):
        assert _newest_mtime(tmp_path) is None

    def test_no_matching_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("hello")
        assert _newest_mtime(tmp_path) is None  # default glob is *.py

    def test_single_file(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("x")
        result = _newest_mtime(tmp_path)
        assert result is not None
        assert abs(result - f.stat().st_mtime) < 1

    def test_newest_of_multiple(self, tmp_path):
        old = tmp_path / "old.py"
        old.write_text("old")
        # Force older mtime
        os.utime(old, (time.time() - 86400, time.time() - 86400))

        new = tmp_path / "new.py"
        new.write_text("new")

        result = _newest_mtime(tmp_path)
        assert result is not None
        assert abs(result - new.stat().st_mtime) < 1

    def test_custom_glob(self, tmp_path):
        (tmp_path / "foo.py").write_text("x")
        (tmp_path / "bar.md").write_text("y")
        assert _newest_mtime(tmp_path, "*.md") is not None
        assert _newest_mtime(tmp_path, "*.txt") is None


class TestDaysSince:
    def test_now_is_zero(self):
        assert _days_since(time.time()) == 0

    def test_one_day_ago(self):
        # int() truncation may give 0 or 1 depending on sub-second timing
        assert _days_since(time.time() - 86400) in (0, 1)

    def test_two_days_ago(self):
        assert _days_since(time.time() - 2 * 86400) >= 1

    def test_thirty_days_ago(self):
        result = _days_since(time.time() - 30 * 86400)
        assert 29 <= result <= 30
