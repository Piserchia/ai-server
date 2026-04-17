# Runner patterns

## When to use this
Extending the runner with new post-session hooks (write-back, review, escalation, etc.).

## The pattern: spawn a child job, link via parent_job_id

The runner wraps `run_session` in `_process_job`. After the session terminates
(success or failure), it can enqueue **child jobs** for follow-up work. The
pattern, used by `_verify_writeback` and `_maybe_escalate`:

```python
async def _my_post_hook(job: Job, result: dict) -> None:
    # 1. Decide whether to act. If no, return silently.
    if not _should_spawn_child(job, result):
        return

    # 2. Enqueue the child via the shared gateway helper.
    child = await enqueue_job(
        description="...",
        kind="_my_child_kind",       # leading underscore → internal skill
        payload={...},
        project_id=job.project_id,
        created_by=f"myhook:{str(job.id)[:8]}",
    )

    # 3. Link child → parent.
    async with session_scope() as s:
        await s.execute(
            update(Job).where(Job.id == child.id).values(parent_job_id=job.id)
        )

    # 4. Audit-log the spawn on the PARENT's log.
    audit_log.append(
        str(job.id), "<hook_name>_spawned",
        child_job_id=str(child.id),
        ...context fields...,
    )
```

## Why this works (and why inline-do-the-work doesn't)

- **Audit trail**: every child gets its own audit log file + summary. You can
  trace "what did the follow-up session do?" independently.
- **Cost accounting**: resolved_model/effort are recorded per job. An `escalated_from`
  retry shows up as a separate row, making the auto-tuning query simple.
- **Failure isolation**: if the child fails, the parent is already completed.
  No cascade.
- **Recursion guarded by payload flag**: `escalated_from` and `_writeback`-as-kind
  prevent loops. Always include a similar guard in new hooks.
- **User-visible in the dashboard**: child jobs appear as rows with
  `created_by="myhook:abc12345"` so it's clear what spawned them.

## Skip conditions every hook should honor

- `job.kind == "chat"` — chats are ephemeral, no hooks should fire
- `job.kind == "_writeback"` — internal; skipping prevents write-back of write-back
- `job.resolved_skill` starts with `_` — any internal skill is off-limits for further hooks
- `(job.payload or {}).get("escalated_from")` — this job is already a retry
- `(job.payload or {}).get("no_post_hooks")` — explicit opt-out flag callers can set

Wrap the hook call site in try/except and log non-fatally. A hook error must
never prevent the primary job from being marked complete.
