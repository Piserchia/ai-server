"""Tasks and task turns tables for multi-turn interaction.

Revision ID: 003
Revises: 002
Create Date: 2026-04-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="active",
        ),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("chat_id", sa.BigInteger, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_created_at", "tasks", ["created_at"])

    op.create_table(
        "task_turns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id", UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("turn_number", sa.SmallInteger, nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "job_id", UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("task_id", "turn_number", name="uq_task_turn"),
    )

    # Add task_id to jobs table
    op.add_column(
        "jobs",
        sa.Column(
            "task_id", UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_jobs_task_id", "jobs", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_task_id", table_name="jobs")
    op.drop_column("jobs", "task_id")
    op.drop_table("task_turns")
    op.drop_index("ix_tasks_created_at", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")
