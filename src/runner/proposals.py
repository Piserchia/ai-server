"""
Proposal tracking helpers.

Pure functions + async DB helpers for the Rec-10 feedback loop:
- Skills like `review-and-improve` insert proposals.
- Skills like `server-patch` mark them applied when PRs merge.
- The `/proposals` Telegram command queries them.

The parsing logic (extract_proposal_id) is pure and unit-tested. DB
operations are async and integration-tested only.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update, and_

from src.db import async_session
from src.models import Proposal, ProposalChangeType, ProposalOutcome


_PROPOSAL_ID_RE = re.compile(
    r"proposal[\s\-_]*id\s*[:=]\s*"
    r"([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})",
    re.IGNORECASE,
)


def extract_proposal_id(text: str) -> Optional[uuid.UUID]:
    """Parse a `Proposal-ID: <uuid>` marker out of arbitrary text.

    Returns a UUID if a well-formed one is found, None otherwise. Case-
    insensitive on both the key and the hex. Tolerates dashes, underscores,
    or spaces between "Proposal" and "ID". Tolerates `:` or `=` separator.
    Returns the FIRST match if multiple are present.

    Pure function.
    """
    if not text:
        return None
    match = _PROPOSAL_ID_RE.search(text)
    if not match:
        return None
    raw = match.group(1).replace("-", "").lower()
    if len(raw) != 32:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def is_valid_change_type(change_type: str) -> bool:
    try:
        ProposalChangeType(change_type)
        return True
    except ValueError:
        return False


def is_valid_outcome(outcome: str) -> bool:
    try:
        ProposalOutcome(outcome)
        return True
    except ValueError:
        return False


def format_proposal_line(
    proposal_id: uuid.UUID,
    target_file: str,
    change_type: str,
    outcome: str,
    proposed_at: datetime,
    now: Optional[datetime] = None,
) -> str:
    """Format one proposal for `/proposals` Telegram output. Pure function."""
    if now is None:
        now = datetime.now(timezone.utc)
    if proposed_at.tzinfo is None:
        proposed_at = proposed_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age = now - proposed_at
    if age.days >= 1:
        age_str = f"{age.days}d"
    elif age.total_seconds() >= 3600:
        age_str = f"{int(age.total_seconds() // 3600)}h"
    else:
        age_str = f"{int(age.total_seconds() // 60)}m"

    short_id = str(proposal_id)[:8]
    display_file = target_file if len(target_file) <= 48 else "..." + target_file[-45:]
    return f"{short_id} {outcome:9s} {change_type:18s} {age_str:>5s}  {display_file}"


# ── Async DB operations ────────────────────────────────────────────────────


async def find_recent_duplicate(
    target_file: str,
    change_type: str,
    lookback_days: int = 30,
) -> Proposal | None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    async with async_session() as s:
        result = await s.execute(
            select(Proposal)
            .where(
                and_(
                    Proposal.target_file == target_file,
                    Proposal.change_type == change_type,
                    Proposal.outcome.in_(
                        [ProposalOutcome.pending.value, ProposalOutcome.rejected.value]
                    ),
                    Proposal.proposed_at >= cutoff,
                )
            )
            .order_by(Proposal.proposed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def insert_proposal(
    proposed_by_job_id: uuid.UUID,
    target_file: str,
    change_type: str,
    rationale: str | None = None,
) -> Proposal:
    if not is_valid_change_type(change_type):
        raise ValueError(f"invalid change_type: {change_type}")

    proposal = Proposal(
        proposed_by_job_id=proposed_by_job_id,
        target_file=target_file,
        change_type=change_type,
        rationale=rationale,
        outcome=ProposalOutcome.pending.value,
    )
    async with async_session() as s:
        s.add(proposal)
        await s.commit()
        await s.refresh(proposal)
    return proposal


async def mark_proposal_merged(
    proposal_id: uuid.UUID,
    pr_url: str,
) -> bool:
    async with async_session() as s:
        result = await s.execute(
            update(Proposal)
            .where(
                and_(
                    Proposal.id == proposal_id,
                    Proposal.outcome.in_(
                        [ProposalOutcome.pending.value, ProposalOutcome.rejected.value]
                    ),
                )
            )
            .values(
                outcome=ProposalOutcome.merged.value,
                applied_pr_url=pr_url,
                applied_at=datetime.now(timezone.utc),
            )
        )
        await s.commit()
        return (result.rowcount or 0) > 0


async def list_pending_proposals(limit: int = 50) -> list[Proposal]:
    async with async_session() as s:
        result = await s.execute(
            select(Proposal)
            .where(Proposal.outcome == ProposalOutcome.pending.value)
            .order_by(Proposal.proposed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def list_recent_proposals(
    lookback_days: int = 30,
    limit: int = 50,
) -> list[Proposal]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    async with async_session() as s:
        result = await s.execute(
            select(Proposal)
            .where(Proposal.proposed_at >= cutoff)
            .order_by(Proposal.proposed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_proposal_by_id_prefix(prefix: str) -> Proposal | None:
    from sqlalchemy import text
    if not prefix:
        return None
    try:
        return await _get_by_full_uuid(uuid.UUID(prefix))
    except ValueError:
        pass

    async with async_session() as s:
        result = await s.execute(
            text("SELECT id FROM proposals WHERE CAST(id AS TEXT) LIKE :p LIMIT 2"),
            {"p": f"{prefix}%"},
        )
        ids = [row[0] for row in result.fetchall()]
        if len(ids) != 1:
            return None
        return await s.get(Proposal, ids[0])


async def _get_by_full_uuid(pid: uuid.UUID) -> Proposal | None:
    async with async_session() as s:
        return await s.get(Proposal, pid)
