"""
Typed capture of the Claude Agent SDK `ResultMessage` + the one terminal-reason
vocabulary (Observability Phase 1 B2; spec §2.4 / §2.7; P0 plan Task 2 re-cut).

Pure functions only — no SDK import, no I/O — so the terminal-reason and
served-model logic is testable with a fake message. Wiring (B3):
  - session._run_in_process → capture_result_message(message,
                              api_retry_error=<last system/api_retry category>)
                              + served_model_violation
  - session.run_session     → derive_terminal_reason(capture) +
                              result_columns(capture, cost_usd_list=pricing.price_usage(…))
                              on the Anthropic lane; usage_columns(usage) on the
                              executor lane (which keeps ExecResult.terminal_reason)
  - main._process_job       → terminal_reason_for_exception on the generic
                              Anthropic failure branch

This module never prices anything: `cost_usd_list` is computed by
src/runner/pricing.py and passed in (spec §2.8 gives that column exactly one
definition), and the SDK's own `total_cost_usd` is carried through to the
separate `sdk_cost_usd` column. The only pricing import is
`cache_write_buckets`, so both lanes split cache writes by one rule.

Field names are those of claude_agent_sdk ResultMessage: subtype, duration_ms,
duration_api_ms, is_error, num_turns, stop_reason, total_cost_usd, usage,
result, model_usage (CLI key `modelUsage`), permission_denials, errors,
api_error_status. Every read is getattr-with-default so an older/newer CLI
shape degrades to NULL columns, never a crash.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from src.runner import pricing

# jobs.terminal_reason (String(32), migration 007) vocabulary — spec §2.4's 13
# plus `review_blocked` / `publish_failed`, which the tree already stamps and
# the pre-push gate + Telegram/web badges pin (D-P1-1). The Codex lane's
# `codex_cli.TERMINAL_REASONS` is a subset (pinned by a test, not an assert).
TERMINAL_REASONS: tuple[str, ...] = (
    "ok", "max_turns", "interrupted", "timeout", "api_error",
    "rate_limited", "auth_expired", "unrecognized_model",
    # Vendor enforcement (spec §2.4). These three are NOT derivable from an
    # HTTP status — an account hold and an expired login are both 403 — so
    # they come from the `error` CATEGORY the CLI puts on its system/api_retry
    # messages. Phase 1 records the reason; the lane hold and the
    # provider_enforcement notice are Phase 3.
    "account_on_hold", "oauth_revoked", "billing_error",
    "provider_refused", "error", "review_blocked", "publish_failed",
)

# system/api_retry `error` category → terminal_reason. The single place the
# alias is defined: `oauth_revoked` is our name for the vendor's
# `oauth_org_not_allowed` — one signal, two vocabularies, written down here
# so nobody reads them as two.
API_RETRY_TO_TERMINAL: dict[str, str] = {
    "rate_limit": "rate_limited",
    "overloaded": "api_error",
    "account_on_hold": "account_on_hold",
    "oauth_org_not_allowed": "oauth_revoked",
    "billing_error": "billing_error",
    "authentication_failed": "auth_expired",
}

# The terminal reasons that mean the vendor is enforcing against the account
# (B3 raises on these after the banner belt; Phase 3 holds the lane).
ENFORCEMENT_CATEGORIES: frozenset[str] = frozenset(
    {"account_on_hold", "oauth_revoked", "billing_error"})

# terminal_reason_for_exception anchors: the `api_retry <category>` token the
# session's raise text carries, and the word-bounded auth signals (the Codex
# lane's `classify_error` uses the same discipline).
_API_RETRY_IN_TEXT = re.compile(r"\bapi_retry ([a-z_]+)")
_AUTH_SIGNAL_RE = re.compile(r"\b401\b|\b403\b|\bexpired\b|unauthori[sz]ed")

_USAGE_TOKEN_KEYS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def usage_is_empty(usage: dict | None) -> bool:
    """True when a session's usage dict shows no real work.

    Pure function (relocated from `session.py`, which re-exports it).
    Considers input / output / cache-read / cache-creation tokens; a real
    session (even a trivial one) consumes at least the system-prompt input,
    so all-zero across the four is the SDK's signature for "we never actually
    made it through a live Anthropic call". Missing or non-integer values
    count as zero (SDK versions vary).
    """
    if not usage:
        return True
    for key in _USAGE_TOKEN_KEYS:
        try:
            if int(usage.get(key) or 0) > 0:
                return False
        except (TypeError, ValueError):
            continue
    return True


# `jobs.cli_version` is VARCHAR(24) (migration 008; `src/models.py`). Pinned
# against the ORM by tests/test_result_capture.py::TestCliVersionColumn.
CLI_VERSION_MAX = 24
_VERSION_TOKEN = re.compile(r"^v?\d+\.\d+")


def cli_version_column(raw: str | None) -> str | None:
    """`jobs.cli_version` for EITHER lane from whatever the lane reports.

    The Anthropic lane reports a bare `2.1.139`; the Codex lane reports
    `codex --version`'s first line, `codex-cli 0.162.0-alpha.17.2` — 28 chars,
    which overflowed the 24-char column on the first real Codex job after the
    Phase-1 deploy (prod 2026-10-28, job 0e09233d) and failed a job whose work
    was done. So: the first version-shaped token (the version, without the
    tool name or a trailing annotation; else the last token), clipped to the
    column, None when empty.
    """
    text = (raw or "").strip()
    if not text:
        return None
    tokens = text.split()
    # The first version-shaped token wins (`codex-cli 0.170.0 (abc123)` →
    # `0.170.0`); with none, the last token (`unknown` stays `unknown`).
    pick = next((t for t in tokens if _VERSION_TOKEN.match(t)), tokens[-1])
    return pick[:CLI_VERSION_MAX] or None


def usage_columns(usage: dict[str, Any] | None) -> dict[str, int]:
    """The five token columns (migration 008) from an SDK-named usage dict of
    EITHER lane — the SDK's own `ResultMessage.usage` or `codex_cli.map_usage`
    output. Cache writes are split by `pricing.cache_write_buckets`: the nested
    `cache_creation.ephemeral_{1h,5m}` object when present, else the flat
    `cache_creation_input_tokens` into the 1-h arm (spec §2.8).
    `reasoning_output_tokens` has no column and is ignored. Capture-free so the
    executor lane can stamp the same keys without a ResultMessage."""
    w1h, w5m = pricing.cache_write_buckets(usage)
    return {
        "input_tokens": _int((usage or {}).get("input_tokens")),
        "output_tokens": _int((usage or {}).get("output_tokens")),
        "cache_read_tokens": _int((usage or {}).get("cache_read_input_tokens")),
        "cache_write_1h_tokens": w1h,
        "cache_write_5m_tokens": w5m,
    }


@dataclass(frozen=True)
class ResultCapture:
    subtype: str = "success"
    is_error: bool = False
    num_turns: int | None = None
    duration_ms: int | None = None
    duration_api_ms: int | None = None
    total_cost_usd: float | None = None
    stop_reason: str | None = None
    api_error_status: int | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    model_usage: dict[str, Any] = field(default_factory=dict)
    permission_denials: int = 0
    result_text: str = ""
    errors: tuple[str, ...] = ()
    # Not a ResultMessage field: the session's last system/api_retry `error`
    # category, passed in by the caller so the enforcement signal travels with
    # the capture (spec §2.4).
    api_retry_error: str | None = None

    @property
    def input_tokens(self) -> int:
        return _int(self.usage.get("input_tokens"))

    @property
    def output_tokens(self) -> int:
        return _int(self.usage.get("output_tokens"))

    @property
    def cache_read_tokens(self) -> int:
        return _int(self.usage.get("cache_read_input_tokens"))

    @property
    def cache_write_1h_tokens(self) -> int:
        """1-hour cache writes — the TTL the subscription actually uses
        (`pricing.cache_write_buckets`: nested object first, flat key → 1 h)."""
        return pricing.cache_write_buckets(self.usage)[0]

    @property
    def cache_write_5m_tokens(self) -> int:
        """5-minute cache writes — 0 on this account; non-zero is the
        usage-credits signature (spec §2.8 metered-spend tripwires)."""
        return pricing.cache_write_buckets(self.usage)[1]

    @property
    def usage_empty(self) -> bool:
        """Same predicate as `usage_is_empty`: all four counters zero."""
        return usage_is_empty(self.usage)

    @property
    def model_served(self) -> str | None:
        return dominant_model(self.model_usage)

    @property
    def usage_by_model(self) -> dict[str, dict[str, Any]]:
        """`usage_by_model(self.model_usage)` — the per-model breakdown."""
        return usage_by_model(self.model_usage)


_MODEL_USAGE_TOKEN_KEYS = (
    "inputTokens", "input_tokens",
    "outputTokens", "output_tokens",
    "cacheReadInputTokens", "cache_read_input_tokens",
    "cacheCreationInputTokens", "cache_creation_input_tokens",
)


def dominant_model(model_usage: dict[str, Any] | None) -> str | None:
    """The model that did the session's work: the `model_usage` entry with the
    most tokens, NOT the first key.

    The bundled CLI makes its own small-model calls inside a session, so
    `model_usage` routinely carries a second, tiny entry — on prod that is the
    retired haiku-4-5 utility id — and it is often FIRST in the dict. Taking
    `next(iter(...))` therefore stamped haiku as `jobs.model_served` on 39 of
    111 jobs in Phase 1's first week (2026-10-22..28) and, because
    `pricing.price_usage` keys on `model_served`, priced Opus and Sonnet work
    at Haiku rates — understating that week's ledger by ≈ $97 of $122. Summing
    the four token counters (either naming) makes the auxiliary entry lose by
    orders of magnitude; cost and context-window fields are ignored.

    Degenerate shapes keep the old behaviour: with no countable tokens
    anywhere (values absent, empty or non-numeric) the first key wins, so a
    `{"<model>": {}}` capture still reports that model.
    """
    if not model_usage:
        return None
    best: str | None = None
    best_tokens = -1
    for name, stats in model_usage.items():
        total = 0
        if isinstance(stats, dict):
            for key in _MODEL_USAGE_TOKEN_KEYS:
                value = stats.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                total += int(value)
        if total > best_tokens:
            best, best_tokens = name, total
    return best


_MODEL_USAGE_KEY_MAP = {
    "inputTokens": "input_tokens", "input_tokens": "input_tokens",
    "outputTokens": "output_tokens", "output_tokens": "output_tokens",
    "cacheReadInputTokens": "cache_read_input_tokens",
    "cache_read_input_tokens": "cache_read_input_tokens",
    "cacheCreationInputTokens": "cache_creation_input_tokens",
    "cache_creation_input_tokens": "cache_creation_input_tokens",
}
_USAGE_KEYS = ("input_tokens", "output_tokens",
               "cache_read_input_tokens", "cache_creation_input_tokens")
_MODEL_COST_KEYS = ("costUSD", "cost_usd", "sdk_cost_usd")


def usage_by_model(model_usage: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """`ResultMessage.model_usage` normalised to the SDK's usage key names:
    `{<model id>: {input_tokens, output_tokens, cache_read_input_tokens,
    cache_creation_input_tokens[, sdk_cost_usd]}}`.

    The CLI reports camelCase counters next to non-counters; the four
    counters are kept (a missing or non-numeric one is 0) plus the CLI's own
    per-model cost (`costUSD` → `sdk_cost_usd`, only when numeric — the one
    figure that lets a reconcile compare computed-vs-SDK per model);
    `contextWindow`/`webSearchRequests` drop. Already-normalised input passes
    through; an entry that is not a dict, or an empty model id, is dropped.
    Per-model cache writes have no TTL split (only the aggregate
    `usage.cache_creation` does), so the flat count is what
    `pricing.cache_write_buckets` puts in the 1-h arm.

    What the bundled CLI (2.1.139) puts here, read from its source during
    review 2026-10-28, stated not asserted: `usage` accumulates the main
    loop's own messages only, while `modelUsage` accumulates EVERY API call
    in the process — Agent-tool subagents and the CLI's utility calls
    included — so in prod this breakdown is a superset of `usage`.

    This is what `job_completed.model_usage` and `result["model_usage"]`
    carry since 2026-10-28, so a multi-model session can be priced per model
    (`pricing.price_model_usage`) instead of as one model.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, stats in (model_usage or {}).items():
        if not name or not isinstance(stats, dict):
            continue
        row: dict[str, Any] = {k: 0 for k in _USAGE_KEYS}
        for key, value in stats.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            target = _MODEL_USAGE_KEY_MAP.get(key)
            if target is not None:
                row[target] = int(value)
            elif key in _MODEL_COST_KEYS:
                row["sdk_cost_usd"] = float(value)
        out[str(name)] = row
    return out


def capture_result_message(message: Any, *,
                           api_retry_error: str | None = None) -> ResultCapture:
    """Read every field of a ResultMessage-shaped object (getattr, defaulted).
    `api_retry_error` is the session's last system/api_retry category, if any."""
    usage = getattr(message, "usage", None)
    model_usage = getattr(message, "model_usage", None)
    denials = getattr(message, "permission_denials", None) or []
    errors = getattr(message, "errors", None) or []
    return ResultCapture(
        subtype=str(getattr(message, "subtype", "") or "success"),
        is_error=bool(getattr(message, "is_error", False)),
        num_turns=_opt_int(getattr(message, "num_turns", None)),
        duration_ms=_opt_int(getattr(message, "duration_ms", None)),
        duration_api_ms=_opt_int(getattr(message, "duration_api_ms", None)),
        total_cost_usd=_opt_float(getattr(message, "total_cost_usd", None)),
        stop_reason=getattr(message, "stop_reason", None),
        api_error_status=_opt_int(getattr(message, "api_error_status", None)),
        usage=dict(usage) if isinstance(usage, dict) else {},
        model_usage=dict(model_usage) if isinstance(model_usage, dict) else {},
        permission_denials=len(denials) if isinstance(denials, (list, tuple)) else 0,
        result_text=str(getattr(message, "result", "") or ""),
        errors=tuple(str(e) for e in errors) if isinstance(errors, (list, tuple)) else (),
        api_retry_error=(str(api_retry_error) or None) if api_retry_error else None,
    )


def derive_terminal_reason(capture: ResultCapture, *, banner_terminal: bool = False) -> str:
    """Typed terminal reason for the ANTHROPIC lane (the Codex lane keeps
    `ExecResult.terminal_reason`). `banner_terminal` is
    session.is_api_terminal_session(...) — the regex belt kept for one release
    (spec §2.4: 'kept as a belt'). `capture.api_retry_error` is the `error`
    category of the session's last system/api_retry message. It is checked
    first among the FAILURE signals: an account hold, a revoked OAuth grant
    and a billing event are category-borne signals that no HTTP status
    distinguishes (spec §2.4), and the three enforcement reasons outrank the
    status unconditionally. A transient category (`overloaded`, `rate_limit`,
    `authentication_failed`) only labels a session that actually FAILED
    (is_error, an api_error_status, or the banner belt): the CLI emits
    system/api_retry before the retry's outcome is known, so a success-shaped
    capture after a recovered retry is `ok` — the `api_retry` audit row keeps
    the recovered retry (whole-tier review 2026-10-22)."""
    category = (capture.api_retry_error or "").strip().lower()
    mapped = API_RETRY_TO_TERMINAL.get(category)
    status = capture.api_error_status
    failed = capture.is_error or status is not None or banner_terminal
    if mapped and (failed or mapped in ENFORCEMENT_CATEGORIES):
        return mapped
    if status == 429:
        return "rate_limited"
    if status in (401, 403):
        return "auth_expired"
    if status is not None and status >= 500:
        return "api_error"
    if capture.subtype == "error_max_turns" or capture.stop_reason == "max_turns":
        return "max_turns"
    if capture.is_error:
        return "error"
    if banner_terminal:
        return "api_error"
    return "ok"


def same_model(served: str, requested: str) -> bool:
    """Case-insensitive family match: exact, or one id is a prefix of the other
    (the CLI may report a date-suffixed id for an un-suffixed request)."""
    s, r = (served or "").lower(), (requested or "").lower()
    return bool(s) and bool(r) and (s == r or s.startswith(r) or r.startswith(s))


def requested_matches_served(served: str, requested: str) -> bool:
    """same_model, OR a bare family alias the CLI expanded itself: `sonnet`,
    `opus-4-7` (hyphen-bounded token inside the served id). Needed because
    POST /api/jobs and the dispatch MCP pass free-text model strings through
    unvalidated; Telegram expands aliases before enqueue and every SKILL.md
    uses a full id, so this only widens the web/dispatch path."""
    if same_model(served, requested):
        return True
    s, r = (served or "").lower(), (requested or "").lower().strip()
    if not s or not r or r.startswith("claude-"):
        return False
    return f"-{r}-" in f"-{s}-"


def served_model_violation(capture: ResultCapture, requested_model: str, *,
                           final_text: str) -> str | None:
    """The silent-empty-success trap (claude-anthropic.md §7): the pinned CLI
    may answer an unknown model id with a 'success' that has no text, zero
    usage and zero API time. Returns a reason string to fail the job with, or
    None.

    Two regimes, deliberately different:
      * model_usage PRESENT: the requested family (full id or bare alias, see
        requested_matches_served) must appear in it, and a present-but-zero
        result (no API time AND empty usage) is rejected.
      * model_usage ABSENT (older shape): reject only the fully empty
        signature — no text, empty usage, zero API time. All-zero usage WITH
        text (common on short chat jobs) stays a success.
    """
    api_ms = capture.duration_api_ms or 0
    if capture.model_usage:
        if not any(requested_matches_served(k, requested_model) for k in capture.model_usage):
            return (f"model_usage {sorted(capture.model_usage)} does not contain "
                    f"requested {requested_model}")
        if api_ms <= 0 and capture.usage_empty:
            return "model_usage present but duration_api_ms=0 and usage empty"
        return None
    if not (final_text or "").strip() and capture.usage_empty and api_ms <= 0:
        return "empty result: no text, zero usage, duration_api_ms=0 (unknown model id?)"
    return None


def result_columns(capture: ResultCapture, *, terminal_reason: str,
                   cost_usd_list: Any, cli_version: str | None) -> dict[str, Any]:
    """The jobs-row UPDATE payload for a finished Anthropic session: the
    migration-008 columns `cli_version, input_tokens, output_tokens,
    cache_read_tokens, cache_write_1h_tokens, cache_write_5m_tokens, num_turns,
    duration_api_ms, cost_usd_list, sdk_cost_usd` plus 007's `model_served`
    and `terminal_reason`. The five token keys are built through
    `usage_columns` so the executor lane (which calls it directly) cannot drift.

    `cost_usd_list` is the RUNNER's own computation from tokens — the caller
    passes `pricing.price_usage(model, usage)` (Decimal) or None when the model
    id cannot be priced. It has NO default on purpose: spec §2.8 gives
    cost_usd_list exactly one definition, and a default would let a call site
    silently re-introduce the SDK figure the reconcile is supposed to be
    checking against (P0 round-3 #10). The SDK's figure is kept, separately,
    in `sdk_cost_usd`; neither is ever a bill.
    """
    cols: dict[str, Any] = {
        "cli_version": cli_version_column(cli_version),
        "model_served": capture.model_served,
    }
    cols.update(usage_columns(capture.usage))
    cols.update({
        "num_turns": capture.num_turns,
        "duration_api_ms": capture.duration_api_ms,
        "cost_usd_list": cost_usd_list,
        "sdk_cost_usd": capture.total_cost_usd,
        "terminal_reason": terminal_reason,
    })
    return cols


def terminal_reason_for_exception(exc: BaseException) -> str:
    """Map the exceptions main._process_job's generic Anthropic branch catches
    onto TERMINAL_REASONS."""
    name = type(exc).__name__
    if isinstance(exc, asyncio.TimeoutError) or name == "TimeoutError":
        return "timeout"
    if isinstance(exc, asyncio.CancelledError):
        return "interrupted"
    if name == "QuotaExhausted":
        return "rate_limited"
    text = str(exc).lower()
    if "unrecognized_model" in text:
        return "unrecognized_model"
    # The api_retry category, which _run_in_process writes into the message
    # text of the RuntimeError it raises ("session error (<subtype>; api_retry
    # <cat>): …") so a raised session records the same reason a completed one
    # would. Anchored to that shape: a bare substring match would label a
    # git/tool error that merely echoes "rate_limit" (whole-tier review
    # 2026-10-22).
    m = _API_RETRY_IN_TEXT.search(text)
    if m and m.group(1) in API_RETRY_TO_TERMINAL:
        return API_RETRY_TO_TERMINAL[m.group(1)]
    if "api terminal error" in text:
        return "api_error"
    # Generic auth heuristic: only on the session's own raise text and
    # word-bounded (a git "Authentication failed … 403" from workspace
    # creation is infrastructure, not an expired login).
    if text.startswith("session error") and "auth" in text and _AUTH_SIGNAL_RE.search(text):
        return "auth_expired"
    return "error"
