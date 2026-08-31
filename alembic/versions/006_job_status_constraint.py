"""Repair illegal job statuses and constrain jobs.status to the JobStatus enum.

2026-08-31 (EVALUATION_2026-08-30 F2.6): a job was found with
status='succeeded' — not a JobStatus member, written by a session via SQL.
Because dependency promotion only recognises 'completed', its three deferred
children were stranded for 8 days. Repair maps 'succeeded' → 'completed';
the CHECK constraint stops the next invented status at write time.

Revision ID: 006
Revises: 005
Create Date: 2026-08-31
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Keep in sync with src/models.py JobStatus.
_VALID = ("queued", "deferred", "running", "awaiting_user",
          "completed", "failed", "cancelled")


def upgrade() -> None:
    valid_sql = ", ".join(f"'{v}'" for v in _VALID)
    # Repair before constraining (a constraint over dirty data won't validate).
    op.execute("UPDATE jobs SET status = 'completed' WHERE status = 'succeeded'")
    # Anything else unrecognised: fail it loudly rather than guess an outcome.
    op.execute(
        "UPDATE jobs SET status = 'failed', "
        "error_message = COALESCE(error_message, '') || "
        "' [status was not a JobStatus member; normalised by migration 006]' "
        f"WHERE status NOT IN ({valid_sql})"
    )
    op.create_check_constraint(
        "ck_jobs_status_valid", "jobs", f"status IN ({valid_sql})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_jobs_status_valid", "jobs", type_="check")
