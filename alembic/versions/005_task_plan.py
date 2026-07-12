"""Add plan JSON to tasks table (P2 planner/decomposer).

Revision ID: 005
Revises: 004
Create Date: 2026-07-12
"""
from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("tasks", sa.Column("plan", sa.JSON, nullable=True))

def downgrade() -> None:
    op.drop_column("tasks", "plan")
