"""
Executors — one module per non-Anthropic agent CLI the runner can drive
(cross-vendor writer slice T3, 2026-10-21; old spec §2.4).

Each executor module exposes the same adapter shape:

    async def run(job, *, cwd, prompt, model_id, sandbox, timeout_s, on_event)
        -> ExecResult
    async def interrupt(job_id) -> bool

and maps its vendor's event stream onto the EXISTING audit kinds
(`tool_use`, `tool_result`, `text`, `thinking` — C14) so every downstream
parser (`review._summarize_tool_usage`, learning's Write/Edit gate,
`retrospective.parse_read_events`, the dashboard stream) reads a Codex job
exactly like a Claude job.

The Anthropic path is NOT an executor module yet (plan §4a: no `ExecSpec`
extraction in this slice); `session.run_session` dispatches to a module here
only when the resolved provider is not `anthropic` (T4).

Modules:
- `codex_cli` — OpenAI Codex CLI, `codex exec --json`, ChatGPT login.
"""

from src.runner.executors.codex_cli import ExecResult  # noqa: F401  (re-export)

__all__ = ["ExecResult"]
