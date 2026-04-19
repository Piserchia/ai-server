"""Proposal tracking table.

Per docs/EVALUATION_2026-04-18.md § 7 Recommendation 10.

Revision ID: 002
Revises: 001
Create Date: 2026-04-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "proposed_by_job_id", UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("target_file", sa.Text, nullable=False, index=True),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "proposed_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("applied_pr_url", sa.Text, nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "outcome", sa.String(16),
            nullable=False, server_default="pending",
        ),
    )
    op.execute(
        "CREATE INDEX ix_proposals_dedup ON proposals (target_file, change_type) "
        "WHERE outcome IN ('pending', 'rejected')"
    )
    op.create_index("ix_proposals_proposed_at", "proposals", ["proposed_at"])


def downgrade() -> None:
    op.drop_index("ix_proposals_proposed_at", table_name="proposals")
    op.execute("DROP INDEX IF EXISTS ix_proposals_dedup")
    op.drop_table("proposals")
