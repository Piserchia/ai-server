"""Provider columns on jobs (cross-vendor writer slice, T2 "007-lite").

2026-10-21 (docs/superpowers/plans/2026-10-21-cross-vendor-writer-slice.md
§5 T2): three additive, nullable columns so a job records which provider
ran it, how its executor ended, and the model the provider actually served.

- resolved_provider  — "anthropic" | "codex" (registry provider key)
- terminal_reason    — executor outcome: completed | rate_limited |
                       auth_expired | api_error | … (T3/T4 stamp it)
- model_served       — the model id the provider reports back (may differ
                       from the pin: snapshots, aliases)

Backfill: every existing row whose resolved_model is an Anthropic id
(`claude-%`) gets resolved_provider='anthropic'. Anything else — NULL
resolved_model, or an id the registry would not have resolved as Anthropic —
stays NULL (C12: never a default). jobs.status and its 006 CHECK are not
touched.

"-lite": the old spec's migration 007 (observability columns: cost, cache
tiers, origin) stays deferred with Observability Phase 1 (§9 of the plan).

Revision ID: 007
Revises: 006
Create Date: 2026-10-21
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("resolved_provider", sa.String(32), nullable=True))
    op.add_column("jobs", sa.Column("terminal_reason", sa.String(32), nullable=True))
    op.add_column("jobs", sa.Column("model_served", sa.String(64), nullable=True))
    op.execute(
        "UPDATE jobs SET resolved_provider = 'anthropic' "
        "WHERE resolved_model LIKE 'claude-%'"
    )


def downgrade() -> None:
    op.drop_column("jobs", "model_served")
    op.drop_column("jobs", "terminal_reason")
    op.drop_column("jobs", "resolved_provider")
