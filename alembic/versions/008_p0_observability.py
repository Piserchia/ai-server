"""Observability Phase 1: result columns, persisted origin, notifications outbox.

Re-cut plan A1 (docs/superpowers/plans/2026-10-21-observability-phase1-recut.md);
design of record is the P0 plan's Task 1 (docs/superpowers/plans/
2026-09-25-multi-model-platform-p0.md) re-cut against the slice's 007. Spec:
docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md
§2.3.

All additive, all nullable. Adds the ResultMessage columns session.py used
to drop (tokens by cache tier, turns, API duration, the two cost columns),
the persisted job/task origin that replaces the bot's in-process
`_job_to_chat` dict, `queue_wait_ms`, three columns RESERVED for Phase 3
(`lane`, `task_class`, `first_event_at` — stay NULL until then), and the
`notifications` outbox the bot drains (A4–A6).

NOT re-added here: `resolved_provider`, `terminal_reason`, `model_served` —
they exist since 007 (`op.add_column` would raise DuplicateColumn on prod).
NOT added at all: `priority` (lanes replace it), `executor`, `sensitivity`
(deleted vendor scope). jobs.status and its 006 CHECK are untouched: done-ness
and the terminal reason are columns, never statuses.

Backfills (Postgres only — guarded by dialect so the SQLite layer-1b test
harness round-trips the module):
- tokens from `jobs.result->'usage'` (2228 of 2231 completed prod rows carry
  the nested `cache_creation.ephemeral_{1h,5m}` buckets; Codex rows have flat
  usage and no nested bucket → 1h/5m stay NULL, correct);
- job origin from `created_by` (byte-equivalent to
  `gateway.jobs.origin_from_created_by`, so old and new rows agree);
- task origin from `chat_id` / `thread_message_id`.
`num_turns`, the cost columns and `duration_api_ms` are NOT backfillable —
session.py never kept them in `result` — and stay NULL on pre-008 rows.

Rollback rule (re-cut plan §4): revert application code by path, never this
file. If the migration itself must go: `alembic downgrade -1` on prod FIRST,
then remove this file and its line from `alembic/applied_history.txt` in the
same commit.

Revision ID: 008
Revises: 007
Create Date: 2026-10-21
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOB_COLUMNS: list[sa.Column] = [
    sa.Column("cli_version", sa.String(24), nullable=True),
    sa.Column("lane", sa.String(16), nullable=True),                # Phase 3; NULL until then
    sa.Column("origin_channel", sa.String(16), nullable=True),
    sa.Column("origin_ref", sa.String(64), nullable=True),
    sa.Column("origin_thread", sa.String(64), nullable=True),
    sa.Column("queue_wait_ms", sa.Integer, nullable=True),
    sa.Column("first_event_at", sa.DateTime(timezone=True), nullable=True),  # Phase 3
    sa.Column("input_tokens", sa.BigInteger, nullable=True),
    sa.Column("output_tokens", sa.BigInteger, nullable=True),
    sa.Column("cache_read_tokens", sa.BigInteger, nullable=True),
    # ephemeral_1h / ephemeral_5m, priced at their own rates (spec §2.3).
    sa.Column("cache_write_1h_tokens", sa.BigInteger, nullable=True),
    sa.Column("cache_write_5m_tokens", sa.BigInteger, nullable=True),
    sa.Column("num_turns", sa.Integer, nullable=True),
    sa.Column("duration_api_ms", sa.Integer, nullable=True),
    # Runner-computed (pricing.py, 1-h rate) and SDK-reported, side by side.
    sa.Column("cost_usd_list", sa.Numeric(10, 4), nullable=True),
    sa.Column("sdk_cost_usd", sa.Numeric(10, 4), nullable=True),
    sa.Column("task_class", sa.String(32), nullable=True),          # Phase 3; NULL until then
]

_TASK_COLUMNS: list[sa.Column] = [
    sa.Column("origin_channel", sa.String(16), nullable=True),
    sa.Column("origin_ref", sa.String(64), nullable=True),
    sa.Column("origin_thread", sa.String(64), nullable=True),
    sa.Column("awaiting_since", sa.DateTime(timezone=True), nullable=True),
]

# Backfill tokens from result->'usage' (Anthropic usage keys; see
# session.py _USAGE_TOKEN_KEYS). Only rows whose values are all digit strings
# are touched — anything else stays NULL rather than failing the migration on
# one odd row.
#
# Cache writes split by TTL (spec §2.3, §2.8): the nested
# usage.cache_creation.ephemeral_{1h,5m}_input_tokens are authoritative. When
# the nested object is absent (older rows) the flat
# cache_creation_input_tokens goes into the 1-h arm and 5-m stays NULL —
# verified against prod's job_completed events carrying cache_creation: the
# flat key equals the 1-h figure to the token and 5-m is 0. Assigning the
# flat value to 5-m instead would misprice every backfilled row by ~40 %
# ($10/M 1-h Opus vs $6.25/M 5-m).
_BACKFILL_TOKENS = """
UPDATE jobs SET
  input_tokens          = NULLIF(result->'usage'->>'input_tokens', '')::bigint,
  output_tokens         = NULLIF(result->'usage'->>'output_tokens', '')::bigint,
  cache_read_tokens     = NULLIF(result->'usage'->>'cache_read_input_tokens', '')::bigint,
  cache_write_1h_tokens = COALESCE(
      NULLIF(result->'usage'->'cache_creation'->>'ephemeral_1h_input_tokens', '')::bigint,
      NULLIF(result->'usage'->>'cache_creation_input_tokens', '')::bigint),
  cache_write_5m_tokens =
      NULLIF(result->'usage'->'cache_creation'->>'ephemeral_5m_input_tokens', '')::bigint
WHERE input_tokens IS NULL
  AND jsonb_typeof(result->'usage') = 'object'
  AND COALESCE(result->'usage'->>'input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->>'output_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->>'cache_read_input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->>'cache_creation_input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->'cache_creation'->>'ephemeral_1h_input_tokens', '0') ~ '^[0-9]+$'
  AND COALESCE(result->'usage'->'cache_creation'->>'ephemeral_5m_input_tokens', '0') ~ '^[0-9]+$'
"""

# Equivalent to gateway.jobs.origin_from_created_by over the producer
# vocabulary: `telegram:<chat>` → ('telegram', <chat>); `web` → ('web', NULL);
# `scheduler` → ('scheduler', NULL); everything else (dispatch-mcp,
# event-trigger*, learning:, writeback:, escalation*, plan:, evaluator:,
# eval-fix:, auto-continue:, bot-error-handler, deploy-autopilot, owner-*) →
# ('system', LEFT(created_by, 64)). The `web`/`scheduler` ref arm is an
# explicit NULL (whole-tier review 2026-10-22: without it the ELSE stamped the
# literal `web`/`scheduler` as origin_ref, so backfilled rows disagreed with
# A2's fresh stamps). NULLIF on the other ref arms: a bare `telegram:` (or
# empty created_by) gives origin_ref NULL, exactly what the Python helper
# returns. Not byte-identical outside the vocabulary: `split_part(…, ':', 2)`
# takes the second colon field untrimmed where Python takes everything after
# the first colon and strips it — no producer writes `telegram:a:b` or padded
# ids. tests/test_migrations.py pins the arms textually.
_BACKFILL_ORIGIN = """
UPDATE jobs SET
  origin_channel = CASE
    WHEN created_by LIKE 'telegram:%' THEN 'telegram'
    WHEN created_by = 'web'           THEN 'web'
    WHEN created_by = 'scheduler'     THEN 'scheduler'
    ELSE 'system' END,
  origin_ref = CASE
    WHEN created_by LIKE 'telegram:%' THEN NULLIF(LEFT(split_part(created_by, ':', 2), 64), '')
    WHEN created_by IN ('web', 'scheduler') THEN NULL
    ELSE NULLIF(LEFT(created_by, 64), '') END
WHERE origin_channel IS NULL
"""

_BACKFILL_TASK_ORIGIN = """
UPDATE tasks SET
  origin_channel = 'telegram',
  origin_ref = chat_id::text,
  origin_thread = thread_message_id::text
WHERE origin_channel IS NULL AND chat_id IS NOT NULL
"""


def upgrade() -> None:
    for col in _JOB_COLUMNS:
        op.add_column("jobs", col)
    for col in _TASK_COLUMNS:
        op.add_column("tasks", col)

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notice_kind", sa.String(32), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=True),     # job | task | schedule | ops
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("severity", sa.String(8), nullable=False, server_default="info"),
        sa.Column("body", sa.Text, nullable=False),
        # JSONB on Postgres; plain JSON on the SQLite test harness.
        sa.Column("actions", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False, server_default="telegram"),
        sa.Column("target", sa.String(64), nullable=True),
        sa.Column("thread", sa.String(64), nullable=True),
        sa.Column("external_ref", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        # sa.func.now() → now() on Postgres, CURRENT_TIMESTAMP on SQLite.
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_pending", "notifications", ["status", "created_at"],
                    postgresql_where=sa.text("status = 'pending'"))

    # Postgres-only SQL (`->`, jsonb_typeof, `~`, split_part, `::text`); the
    # SQLite layer-1b harness skips the backfills and round-trips the DDL.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_BACKFILL_TOKENS)
        op.execute(_BACKFILL_ORIGIN)
        op.execute(_BACKFILL_TASK_ORIGIN)


def downgrade() -> None:
    op.drop_index("ix_notifications_pending", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_table("notifications")
    for col in reversed(_TASK_COLUMNS):
        op.drop_column("tasks", col.name)
    for col in reversed(_JOB_COLUMNS):
        op.drop_column("jobs", col.name)
