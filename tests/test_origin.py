"""
Persisted job/task origin — Observability Phase 1 (re-cut plan A1/A2).

A1 lands the two pure helpers in `src/gateway/jobs.py`:
`ORIGIN_CHANNELS` and `origin_from_created_by(created_by)`. Nothing calls
them in A1; A2 wires them into `enqueue_job`. The mapping here is the one
migration 008's `_BACKFILL_ORIGIN` CASE implements in SQL, so backfilled
and new rows agree (tests/test_migrations.py pins the SQL side textually).

The `created_by` vocabulary below is every producer in the current tree
(grep `created_by=` under src/ and scripts/): the three channels with a
literal spelling (`telegram:<chat>`, `web`, `scheduler`) and the long tail
of internal producers that all map to `system` with the raw value as ref.
"""

from __future__ import annotations

import pytest

from src.gateway.jobs import ORIGIN_CHANNELS, origin_from_created_by


class TestOriginFromCreatedBy:
    @pytest.mark.parametrize("created_by,expected", [
        # The three literal channels.
        ("telegram:123456789", ("telegram", "123456789")),
        ("telegram:", ("telegram", None)),              # bare prefix → NULL ref (NULLIF arm)
        ("telegram:  42  ", ("telegram", "42")),       # whitespace never lands in a ref
        ("web", ("web", None)),
        ("scheduler", ("scheduler", None)),
        # Everything else is `system` with the raw created_by as the ref.
        ("dispatch-mcp", ("system", "dispatch-mcp")),
        ("event-trigger", ("system", "event-trigger")),
        ("event-trigger:deploy", ("system", "event-trigger:deploy")),
        ("learning:abcd1234", ("system", "learning:abcd1234")),
        ("writeback:abcd1234", ("system", "writeback:abcd1234")),
        ("escalation", ("system", "escalation")),
        ("escalation:abcd1234", ("system", "escalation:abcd1234")),
        ("plan:abcd1234", ("system", "plan:abcd1234")),
        ("evaluator:abcd1234", ("system", "evaluator:abcd1234")),
        ("eval-fix:abcd1234", ("system", "eval-fix:abcd1234")),
        ("auto-continue:abcd1234", ("system", "auto-continue:abcd1234")),
        ("bot-error-handler", ("system", "bot-error-handler")),
        ("deploy-autopilot", ("system", "deploy-autopilot")),
        ("owner-dm", ("system", "owner-dm")),
        ("unknown", ("system", "unknown")),
        # Degenerate inputs never produce an empty-string ref.
        ("", ("system", None)),
        ("   ", ("system", None)),
        (None, ("system", None)),
    ])
    def test_mapping(self, created_by, expected):
        assert origin_from_created_by(created_by) == expected

    def test_ref_fits_column(self):
        # jobs.origin_ref is String(64); a long created_by is clipped, never
        # rejected (the column itself is also String(64)).
        channel, ref = origin_from_created_by("owner-" + "x" * 200)
        assert channel == "system" and len(ref) <= 64

    def test_telegram_ref_fits_column(self):
        channel, ref = origin_from_created_by("telegram:" + "9" * 200)
        assert channel == "telegram" and len(ref) == 64

    def test_every_channel_is_declared(self):
        seen = {origin_from_created_by(cb)[0] for cb in
                ("telegram:1", "web", "scheduler", "dispatch-mcp", "")}
        assert seen <= set(ORIGIN_CHANNELS)
        assert ORIGIN_CHANNELS == ("telegram", "web", "cli", "scheduler", "system")
        assert all(len(c) <= 16 for c in ORIGIN_CHANNELS)   # origin_channel is String(16)
