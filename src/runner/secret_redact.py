"""
Secret redaction for the durable trace — E6 (spec §2.4 "Audit/stream
redaction", §8.3 redactor; design of record P0 plan Task 20 + the re-cut E6
Deltas: both lanes).

ALWAYS ON — no switch turns it off. Trace text (never a file, never the job
result) may show `[REDACTED]` inside a code snippet — `password = get_pw()`
in a Write — which is the accepted cost. Every assistant `text`, `thinking`,
`tool_use.input` and `tool_result` preview passes through `redact()` /
`redact_tree()` before it is appended to volumes/audit_log/<id>.jsonl or
published to jobs:stream:<id>, on the Anthropic lane (`session._handle_message`)
and the Codex lane (`codex_cli.default_sink`), so a `printenv` or a
`curl -H 'Authorization: …'` in any skill cannot leave a credential in the
JSONL, the stream, `ai-mcp` reads, or the learning extractor's input. A leaked
CLAUDE_CODE_OAUTH_TOKEN is a ONE-YEAR credential.

The NAME is kept and only the VALUE is replaced, so the trace still says which
variable was set — that is the finding a debugger needs. `final_text_chunks`
(the job result and the TASK_COMPLETE marker-parser input) is deliberately NOT
redacted; the canary sink (`codex_cli.run_canary`) is deliberately NOT
redacted either — it asserts the sentinel's ABSENCE in a scrubbed clone.

Pure module: no I/O, no src imports (session.py and codex_cli.py import it).
The name set is pinned by tests/test_audit_redactor.py to be a superset of
`codex_cli.DENIED_ENV_PREFIXES ∪ DENIED_ENV_NAMES ∪ CANARY_SENTINEL_NAMES` —
two contracts (child-env scrub vs trace redaction), one name set.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

#: Name prefixes whose every variable is a credential or a credential-bearing
#: setting. Kept as a literal here so this module stays import-free.
NAME_PREFIXES: tuple[str, ...] = (
    "CLAUDE_CODE_", "ANTHROPIC_", "GEMINI_", "CEREBRAS_", "GROQ_", "CODEX_",
    "OPENROUTER_", "OPENAI_", "XAI_", "TELEGRAM_", "POSTGRES_", "ALPACA_",
    "TRADIER_", "FINNHUB_", "WEB_AUTH_",
)
#: Name suffixes that mark a credential whatever the prefix (`*_URL`: a DSN
#: carries its password in the URL — DATABASE_URL, REDIS_URL).
NAME_SUFFIXES: tuple[str, ...] = ("_TOKEN", "_SECRET", "_API_KEY", "_PASSWORD", "_URL", "_DSN")

_NAME_ALTS = (
    "(?:" + "|".join(re.escape(p) for p in NAME_PREFIXES) + r")[A-Za-z0-9_]*"
    + r"|[A-Za-z0-9_]*(?:" + "|".join(re.escape(s) for s in NAME_SUFFIXES) + ")"
)
# Separator between a name and its value: `=`, `:`, `=>` (plutil / launchctl
# print), a tab, with optional ANSI colour codes (grep --color) in between.
_SEP = r"(?:\x1b\[[0-9;]*m)*\s*(?:=>|[:=]|\t)\s*"
# A value: a quoted string (spaces allowed) or a run of non-space, non-quote.
_VALUE = r"(?:\"[^\"]*\"|'[^']*'|[^\s\"'\\]+)"   # a backslash ends a bare value: a json.dumps'd `\n`

# A bare Anthropic key anywhere in free text — the whole token goes.
_BARE_KEY = re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}")

# A private key of ANY armour (PEM, OpenSSH, PGP `… BLOCK`), body and all — and
# a body cut short by the 500-char preview (no END armour) too: the body is
# base64 + whitespace, lazily, up to the END line or the first character that
# is not base64 (the `... [N more]` cut marker). The deploy key at
# ~/.config/ai-server/publish-key is a FILE, so its exposure is a `cat`/`Read`
# in an unhooked session; the PATH is kept — which key was read is the finding.
_PEM = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----"
    r"[A-Za-z0-9+/=\s]*?"
    r"(?:-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|(?![A-Za-z0-9+/=\s]))")
# An OpenSSH private blob without the armour (some tools print it bare).
_SSH_BLOB = re.compile(r"\bb3BlbnNzaC1rZXk[A-Za-z0-9+/=]{16,}")

# Prefix-preserving patterns: group(1) is kept, the value is replaced.
_PREFIXED: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+"),
    # The Telegram bot token inside its API URL (`curl https://api.telegram.org/bot<token>/getMe`).
    re.compile(r"(api\.telegram\.org/bot)\d+:[A-Za-z0-9_-]+"),
    # `curl -u user:password`.
    re.compile(r"((?:^|\s)-u\s+[^\s:]+:)\S+"),
    # A bare DSN/URL with a password: scheme://user:PASSWORD@host.
    re.compile(r"(\b[a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@]+(?=@)"),
    # `NAME=value` / `export NAME=value` / `NAME: value` / `"NAME" => "value"`
    # at the start of a line — printenv, env, `.env` dumps, YAML, plutil.
    # Case-insensitive: `print(settings)` renders `telegram_bot_token='…'`.
    re.compile(rf"(?im)^(\s*(?:export\s+)?[\"']?(?:{_NAME_ALTS})[\"']?{_SEP}){_VALUE}"),
    # `NAME=value` mid-line: a command line (`FOO=1 GEMINI_API_KEY=x cmd`), a
    # pydantic repr (`Settings(telegram_bot_token='…', …)`), a JSON-escaped
    # `\n` inside a json.dumps'd tool_result.
    re.compile(rf"(?i)(?:(?<=[\s\"'(,;])|(?<=^)|(?<=\\n))((?:{_NAME_ALTS})=\s*){_VALUE}"),
    # `"api_key": "value"` / `token = value` / `secret_access_key = …` in JSON,
    # YAML, INI and prose. `token` must END the key (so `input_tokens=`,
    # `max_tokens:` and `token_count:` never match).
    re.compile(r"(?i)([\"']?(?:[a-z0-9_-]*(?:api[_-]?key|auth[_-]?token|access[_-]?key|secret|password)"
               r"|token)[\"']?\s*[:=]\s*[\"']?)[^\s\"',}&\\]{6,}"),
    # `?token=…` / `&api_key=…` in a URL query string.
    re.compile(r"(?i)([?&](?:token|api[_-]?key|access[_-]?key|secret)=)[^\s&]+"),
)


def redact(text: str) -> str:
    """Pure. Strip credential-shaped values; everything else byte-identical."""
    if not text:
        return text
    out = _BARE_KEY.sub(REDACTED, text)
    # Whole-body patterns first: a PEM block spans lines and base64 that the
    # line-oriented patterns below would walk straight past.
    out = _PEM.sub(REDACTED, out)
    out = _SSH_BLOB.sub(REDACTED, out)
    for pat in _PREFIXED:
        out = pat.sub(lambda m: m.group(1) + REDACTED, out)
    return out


def redact_tree(value: Any) -> Any:
    """redact() over nested dict / list / tuple structures (tool_use.input,
    the Codex sink's event fields). Tuples come back as lists (JSON shape)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): redact_tree(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_tree(v) for v in value]
    return value
