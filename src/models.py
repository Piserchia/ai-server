"""
ORM models. Six tables.

- jobs:        one unit of work. Records model/effort actually used + user rating.
- schedules:   cron recipes that enqueue jobs.
- projects:    registry of hosted projects.
- proposals:   tuning/doc proposals from review-and-improve.
- tasks:       multi-turn conversation wrappers around related jobs.
- task_turns:  individual turns (user, assistant, system) within a task.

Audit trail is JSONL files on disk, not a table. See src/audit_log.py.

Model/effort tracking enables the auto-tuning loop: `review-and-improve` queries
{kind, model, effort, outcome, user_rating, tokens_used} to propose default changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    awaiting_user = "awaiting_user"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.completed, JobStatus.failed, JobStatus.cancelled}


class JobKind(str, Enum):
    """Maps 1:1 to skills (mostly). `task` and `chat` are generic."""

    task = "task"
    chat = "chat"
    research_report = "research_report"
    research_deep = "research_deep"
    new_project = "new_project"
    new_skill = "new_skill"
    app_patch = "app_patch"
    code_review = "code_review"
    self_diagnose = "self_diagnose"
    server_patch = "server_patch"
    server_upkeep = "server_upkeep"
    project_update_poll = "project_update_poll"
    idea_generation = "idea_generation"
    review_and_improve = "review_and_improve"
    backup = "backup"
    restore = "restore"
    notify = "notify"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default=JobKind.task.value)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobStatus.queued.value, index=True
    )

    # Inputs and outputs
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Model/effort actually used (captured by runner after resolution).
    # Enables auto-tuning: which (skill, model, effort) combos yield the best outcomes?
    resolved_skill: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    resolved_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Quality signals
    user_rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # 1-5
    review_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ^ "LGTM" | "changes_requested" | "blocker" (set by code-review sub-agent)

    # Scoping
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True
    )
    parent_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    # ^ For sub-agent jobs; parent_job_id links back to the spawning session.
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # ^ Multi-turn tasks: groups related jobs into a conversation.

    # Provenance
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="jobs", foreign_keys=[project_id])
    schedule = relationship("Schedule", back_populates="jobs", foreign_keys=[schedule_id])


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)

    job_kind: Mapped[str] = mapped_column(String(64), nullable=False, default=JobKind.task.value)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    job_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    project = relationship("Project", foreign_keys=[project_id])
    jobs = relationship("Job", back_populates="schedule", foreign_keys=[Job.schedule_id])


class TaskStatus(str, Enum):
    """Lifecycle of a multi-turn task."""
    active = "active"                    # job running or about to run
    awaiting_user = "awaiting_user"      # job asked a question, waiting for /reply
    pending_approval = "pending_approval"  # job thinks it's done, waiting for /approve
    completed = "completed"              # user approved
    failed = "failed"                    # unrecoverable failure


class ProjectType(str, Enum):
    static = "static"
    service = "service"
    api = "api"


class ProposalChangeType(str, Enum):
    """What a proposal is changing. Drives dedup logic."""
    default_model = "default-model"
    context_files = "context-files"
    frontmatter_tweak = "frontmatter-tweak"
    doc_update = "doc-update"


class ProposalOutcome(str, Enum):
    """Lifecycle state of a proposal."""
    pending = "pending"
    merged = "merged"
    rejected = "rejected"
    superseded = "superseded"

    @property
    def is_terminal(self) -> bool:
        return self in {
            ProposalOutcome.merged,
            ProposalOutcome.rejected,
            ProposalOutcome.superseded,
        }


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    subdomain: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manifest_path: Mapped[str] = mapped_column(String(512), nullable=False)

    last_healthy_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    created_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )

    jobs = relationship("Job", back_populates="project", foreign_keys=[Job.project_id])


class Proposal(Base):
    """A tuning / documentation proposal emitted by `review-and-improve`.

    See docs/EVALUATION_2026-04-18.md § 7 Recommendation 10.
    """

    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    proposed_by_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    target_file: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )
    applied_pr_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    outcome: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ProposalOutcome.pending.value,
    )

    proposer = relationship("Job", foreign_keys=[proposed_by_job_id])


class Task(Base):
    """Multi-turn conversation wrapper around related jobs.

    A task groups one or more jobs into a conversation. User input and
    assistant output are recorded as turns. Context flows forward to new
    jobs via the task log, not by resuming sessions.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskStatus.active.value, index=True
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    chat_id: Mapped[int | None] = mapped_column(nullable=True)
    # ^ Telegram chat_id — persisted so bot restarts don't lose the mapping

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    turns = relationship("TaskTurn", back_populates="task", order_by="TaskTurn.turn_number")
    jobs = relationship("Job", foreign_keys=[Job.task_id])


class TaskTurn(Base):
    """One turn in a multi-turn task conversation."""

    __tablename__ = "task_turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    turn_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    task = relationship("Task", back_populates="turns")
