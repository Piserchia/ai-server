"""Add thread_message_id to tasks table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-20
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("tasks", sa.Column("thread_message_id", sa.BigInteger, nullable=True))

def downgrade() -> None:
    op.drop_column("tasks", "thread_message_id")
