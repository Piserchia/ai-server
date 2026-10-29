"""
Environment posture for every Claude subprocess the server spawns — E7
(spec §2.4/§3, §6 "Startup assertion over the named Anthropic credentials";
design of record P0 plan Task 17 + the re-cut E7 Deltas).

Three things, one import-free module (session.py imports llm_router, so a
helper both need can live in neither):

* `claude_subprocess_env()` — the overlay passed as `ClaudeAgentOptions.env`
  at every construction site (session, router, learning, reviewer, judge; the
  credential canary's E10 options too). In SDK 0.1.x that dict OVERLAYS the
  inherited os.environ — enough for the two flags; Pro/Max sign-ins ship error
  reports and operational metrics ON by default, and proprietary sessions
  (atlas, alpha) must not. The service plists carry the same two keys as the
  belt for anything else that spawns `claude` under the service env.
* `vendor_keys_in(env)` — the names the runner refuses to START with
  (`main._check_subscription_auth`, fail-closed on every one). Vendor keys live
  in `.env` and are read by Settings IN-PROCESS only; anything in os.environ is
  inherited by every Claude subprocess and by every Bash child of every job.
  **Named, never a blanket `ANTHROPIC_*` prefix**: `ANTHROPIC_MAX_SESSIONS`-
  shaped knobs belong in a plist and a prefix rule would take the fleet down
  on that deploy. The spec's `*_TOKEN` glob is NOT adopted: `WEB_AUTH_TOKEN`,
  `TELEGRAM_BOT_TOKEN`, `TRADIER_SANDBOX_TOKEN`, `FINNHUB_TOKEN` are legitimate
  Settings names that `pipenv run` exports (scripts/run.sh now runs with
  `PIPENV_DONT_LOAD_ENV=1` for exactly that reason), and no Settings field
  name is in the set (pinned by a test).

PROD SHAPE, stated: the service plists run `bash -lc …` — a LOGIN shell, which
sources /etc/profile and the user's profile — so a vendor key exported by a
shell profile WOULD refuse the runner at its next restart, and under
launchd's KeepAlive + ThrottleInterval 30 that is a 30-second crash loop of
the runner alone (web/bot never run this check). The runbook's §0 probe
(`bash -lc env | cut -d= -f1 | … vendor_keys_in`) must print `[]` BEFORE the
first restart that carries this check.
* `utility_model_violation()` / `log_utility_model_usage()` — spec §9's exit
  criterion "`model_usage` on utility calls lists only the requested model":
  the router and the learning extractor log + audit a second family
  (`utility_model_usage{call, requested, served_models}`), never fail the call —
  a persisting second family is the harness's own small-model side request,
  a thing to ledger, not an error.

TWO CONTRACTS, stated so nobody merges them: this module's set is what the
RUNNER may not be started with; `executors.codex_cli.DENIED_ENV_*` is what is
scrubbed from a CHILD process's env on the Codex lane (`TELEGRAM_*`,
`POSTGRES_*`, broker keys …). The redactor (`secret_redact`) covers the union
in the trace. Keep them separate on purpose.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

logger = logging.getLogger(__name__)

CLAUDE_SUBPROCESS_ENV: dict[str, str] = {
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_TELEMETRY": "1",
}

# `CODEX_` is deliberately NOT a prefix (review 2026-10-29): `CODEX_BIN`,
# `CODEX_HOME`, `CODEX_SANDBOX_DEFAULT`, `CODEX_RUN_AS_USER` are this repo's own
# Settings knobs and `CODEX_HOME` is the Codex CLI's documented env var; the
# one Codex credential, `CODEX_API_KEY`, is caught by the `_API_KEY` suffix.
# tests/test_claude_env.py pins that no Settings field name is in the set.
VENDOR_KEY_PREFIXES: tuple[str, ...] = (
    "GEMINI_", "CEREBRAS_", "GROQ_", "OPENROUTER_", "OPENAI_", "XAI_",
)
VENDOR_KEY_SUFFIXES: tuple[str, ...] = ("_API_KEY",)
#: The four Anthropic credential names that outrank the Keychain /login for
#: every Bash child of every job — NAMED, never `ANTHROPIC_*`.
VENDOR_KEY_EXACT: tuple[str, ...] = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
)


def claude_subprocess_env() -> dict[str, str]:
    """A fresh copy of the overlay for one ClaudeAgentOptions (callers may
    not mutate the constant)."""
    return dict(CLAUDE_SUBPROCESS_ENV)


def vendor_keys_in(env: Mapping[str, str]) -> list[str]:
    """Pure. Sorted names in `env` the runner refuses to start with."""
    return sorted(
        k for k in env
        if k in VENDOR_KEY_EXACT
        or any(k.startswith(p) for p in VENDOR_KEY_PREFIXES)
        or any(k.endswith(s) for s in VENDOR_KEY_SUFFIXES)
    )


def utility_model_violation(model_usage: Mapping[str, object] | None,
                            requested: str) -> list[str]:
    """Pure. Families in `model_usage` other than the requested one, sorted.
    An EMPTY/absent `model_usage` is not a violation (older CLI shapes omit
    it); an extra family is a finding to ledger, never an error."""
    return sorted(k for k in (model_usage or {}) if k != requested)


def log_utility_model_usage(call: str, *, requested: str,
                            model_usage: Mapping[str, object] | None) -> list[str]:
    """Log (never raise) when a utility call was served by more than the
    requested model. Returns the extra families so the caller can audit them."""
    extra = utility_model_violation(model_usage, requested)
    if extra:
        logger.warning("utility_model_usage call=%s requested=%s served=%s "
                       "(the harness's own side request? ledger it, do not fail the call)",
                       call, requested, sorted(model_usage or {}))
    return extra
