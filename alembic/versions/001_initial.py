"""Initial schema: jobs, schedules, projects.

Includes columns for the effort/model auto-tuning loop:
- jobs.resolved_skill, resolved_model, resolved_effort — what was actually used
- jobs.user_rating — 1-5 from /rate command
- jobs.review_outcome — set by code-review sub-agent
- jobs.parent_job_id — links sub-agent jobs to their parent

Revision ID: 001
Revises:
Create Date: 2026-04-16
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("subdomain", sa.String(128), nullable=False, unique=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("port", sa.Integer, nullable=True),
        sa.Column("manifest_path", sa.String(512), nullable=False),
        sa.Column("last_healthy_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_job_id", UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("cron_expression", sa.String(128), nullable=False),
        sa.Column("job_kind", sa.String(64), nullable=False),
        sa.Column("job_description", sa.Text, nullable=False),
        sa.Column("job_payload", JSONB, nullable=True),
        sa.Column(
            "project_id", UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("paused", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False, server_default="task"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued", index=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        # Auto-tuning columns
        sa.Column("resolved_skill", sa.String(64), nullable=True, index=True),
        sa.Column("resolved_model", sa.String(64), nullable=True),
        sa.Column("resolved_effort", sa.String(16), nullable=True),
        sa.Column("user_rating", sa.SmallInteger, nullable=True),
        sa.Column("review_outcome", sa.String(32), nullable=True),
        # Linkage
        sa.Column(
            "project_id", UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "schedule_id", UUID(as_uuid=True),
            sa.ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("parent_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Self-referencing FK for parent_job_id
    op.create_foreign_key(
        "jobs_parent_job_fk",
        "jobs", "jobs",
        ["parent_job_id"], ["id"],
        ondelete="SET NULL",
    )

    # Cross-table FK for projects.created_by_job_id (created after jobs table exists)
    op.create_foreign_key(
        "projects_created_by_job_fk",
        "projects", "jobs",
        ["created_by_job_id"], ["id"],
        ondelete="SET NULL",
    )

    # Helpful composite index for the auto-tuning query
    # (SELECT outcome-rollup BY resolved_skill, resolved_model, resolved_effort)
    op.create_index(
        "ix_jobs_autotune",
        "jobs",
        ["resolved_skill", "resolved_model", "resolved_effort", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_autotune", table_name="jobs")
    op.drop_constraint("projects_created_by_job_fk", "projects", type_="foreignkey")
    op.drop_constraint("jobs_parent_job_fk", "jobs", type_="foreignkey")
    op.drop_table("jobs")
    op.drop_table("schedules")
    op.drop_table("projects")
