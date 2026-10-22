"""Notification outbox (Observability Phase 1, A4). outbox.py = rows + policy,
telegram.py = renderer + senders, __main__.py = `python -m src.notify send|drain`.
See .context/modules/notify/CONTEXT.md. Re-exports only."""

from src.notify.outbox import (  # noqa: F401
    COMPLETION_DM_CHANNELS,
    NOTICE_KINDS,
    OPS_NOTICE_KINDS,
    Notice,
    build_job_notice,
    build_ops_notice,
    build_task_notice,
    enqueue_notice,
    lane_label,
    should_notify_job,
)
