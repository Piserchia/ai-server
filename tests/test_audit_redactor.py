"""
E6 — always-on audit/stream secret redaction (spec §2.4 "Audit/stream redaction",
§8.3; §9 test gate `test_audit_redactor`; design of record P0 plan Task 20 + the
re-cut E6 Deltas: both lanes, the Codex `default_sink` included, the canary sink
excluded; the name set is a superset of the Codex deny sets).

A `printenv` or a `curl -H 'Authorization: …'` in ANY skill must not land a
credential value in volumes/audit_log/<id>.jsonl or jobs:stream:<id> —
unconditionally: there is no switch that turns redaction off. The NAME is
kept and only the VALUE is replaced, so the trace still says which variable
was set. `final_text_chunks` (the job result / marker-parser input) is
deliberately NOT redacted.

Pure: real SDK dataclasses (constructing them is allowed; spawning the CLI is
not), monkeypatched audit_log / publish. No SDK process, no Redis.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_audit_redactor.py -q
"""

from __future__ import annotations

import json

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from src.runner.secret_redact import REDACTED, redact, redact_tree

PRINTENV = """\
PATH=/usr/bin:/bin
ANTHROPIC_BASE_URL=https://proxy.example.invalid
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAA
GEMINI_API_KEY=AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKE
TELEGRAM_BOT_TOKEN=123456:AAFAKEFAKEFAKEFAKE
POSTGRES_DSN=postgresql+asyncpg://assistant:hunter2@localhost:5432/assistant
DATABASE_URL=postgres://u:p@h/db
REDIS_URL=redis://:redispass@localhost:6379/0
WEB_AUTH_TOKEN=webtoken-FAKE-0001
TRADIER_SANDBOX_TOKEN=tradier-FAKE-0002
FINNHUB_TOKEN=finnhub-FAKE-0003
ALPACA_API_KEY=alpaca-FAKE-0004
HOME=/Users/x
"""
SECRETS = ("sk-ant-oat01-AAAAAAAAAAAAAAAAAAAAAAAA",
           "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKEFAKE",
           "123456:AAFAKEFAKEFAKEFAKE",
           "https://proxy.example.invalid",
           "hunter2", "postgres://u:p@h/db", "redispass",
           "webtoken-FAKE-0001", "tradier-FAKE-0002", "finnhub-FAKE-0003", "alpaca-FAKE-0004")


class TestPatterns:
    def test_printenv_values_are_gone_but_names_remain(self):
        out = redact(PRINTENV)
        for secret in SECRETS:
            assert secret not in out, secret
        # The finding is still legible: which names were set.
        for name in ("ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN", "GEMINI_API_KEY",
                     "TELEGRAM_BOT_TOKEN", "POSTGRES_DSN", "DATABASE_URL", "REDIS_URL",
                     "WEB_AUTH_TOKEN", "TRADIER_SANDBOX_TOKEN", "FINNHUB_TOKEN", "ALPACA_API_KEY"):
            assert f"{name}={REDACTED}" in out, name
        assert "PATH=/usr/bin:/bin" in out and "HOME=/Users/x" in out   # not credentials

    def test_database_and_redis_urls_are_redacted(self):
        # E6 Delta: the `*_URL` names (a DSN carries the password in the URL)
        # and the `POSTGRES_*` prefix join the set.
        assert redact("DATABASE_URL=postgres://u:p@h/db") == f"DATABASE_URL={REDACTED}"
        assert redact("export REDIS_URL=redis://:x@h:6379/0") == f"export REDIS_URL={REDACTED}"
        assert redact("POSTGRES_PASSWORD: hunter2") == f"POSTGRES_PASSWORD: {REDACTED}"

    def test_a_private_key_body_is_gone_and_the_path_survives(self):
        # The publish deploy key is a FILE, so the exposure is a `cat` of it in
        # an unhooked session, and the body matches no NAME=value pattern. The
        # PATH must stay readable (it is the finding); the KEY must not.
        dump = ("$ cat ~/.config/ai-server/publish-key\n"
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAA\n"
                "AAtzc2gtZWQyNTUxOQAAACDFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE=\n"
                "-----END OPENSSH PRIVATE KEY-----\n")
        out = redact(dump)
        assert "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQ" not in out
        assert "BEGIN OPENSSH PRIVATE KEY" not in out
        assert REDACTED in out
        assert "~/.config/ai-server/publish-key" in out

    @pytest.mark.parametrize("armour", ["RSA PRIVATE KEY", "EC PRIVATE KEY",
                                        "PRIVATE KEY", "OPENSSH PRIVATE KEY"])
    def test_every_pem_armour_is_covered(self, armour):
        body = f"-----BEGIN {armour}-----\nQUJD\n-----END {armour}-----"
        assert "QUJD" not in redact(body)

    def test_unarmoured_openssh_blob(self):
        assert "b3BlbnNzaC1rZXktdjEAAAAABG5vbmU" not in redact(
            "key: b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAA")

    def test_bearer_header(self):
        out = redact("curl -H 'Authorization: Bearer sk-ant-api03-ZZZZZZZZZZZZ' https://x")
        assert "sk-ant-api03-ZZZZZZZZZZZZ" not in out and REDACTED in out
        out = redact("Authorization: Bearer ghp_notAnthropicButStillAToken123")
        assert "ghp_notAnthropicButStillAToken123" not in out

    def test_bare_key_anywhere(self):
        assert redact("oops sk-ant-api03-QQQQQQQQQQQQ oops") == f"oops {REDACTED} oops"

    def test_innocent_text_is_byte_identical(self):
        for text in ("", "hello world", "PATH=/bin", "rate=5", "token_count: 12",
                     "the URL is https://example.com", "TASK_COMPLETE: done",
                     "input_tokens=15 output_tokens=9363"):
            assert redact(text) == text, text

    @pytest.mark.parametrize("prefix", __import__("src.runner.secret_redact", fromlist=["NAME_PREFIXES"]).NAME_PREFIXES)
    def test_every_vendor_prefix(self, prefix):
        assert "leaked" not in redact(f"{prefix}SECRET_THING=leaked")
        assert "leaked" not in redact(f"{prefix.lower()}secret_thing=leaked")      # lower-case too

    @pytest.mark.parametrize("suffix", __import__("src.runner.secret_redact", fromlist=["NAME_SUFFIXES"]).NAME_SUFFIXES)
    def test_every_name_suffix(self, suffix):
        assert "leakedvalue" not in redact(f"MY{suffix}=leakedvalue")

    def test_the_lists_are_what_the_docs_say(self):
        from src.runner.secret_redact import NAME_PREFIXES, NAME_SUFFIXES
        assert {"ANTHROPIC_", "GEMINI_", "CEREBRAS_", "GROQ_", "CODEX_", "OPENROUTER_", "OPENAI_",
                "XAI_", "TELEGRAM_", "POSTGRES_", "ALPACA_", "TRADIER_", "FINNHUB_", "WEB_AUTH_",
                "CLAUDE_CODE_"} <= set(NAME_PREFIXES)
        assert {"_TOKEN", "_SECRET", "_API_KEY", "_PASSWORD", "_URL", "_DSN"} <= set(NAME_SUFFIXES)

    def test_mid_line_assignment(self):
        out = redact("FOO=1 GEMINI_API_KEY=abc123 ./run.sh")
        assert "abc123" not in out and "FOO=1" in out and "./run.sh" in out

    def test_json_and_yaml_shapes(self):
        out = redact('{"api_key": "abcdef123456", "n": 3}')
        assert "abcdef123456" not in out and '"n": 3' in out
        out = redact("password = hunter2hunter2")
        assert "hunter2hunter2" not in out

    def test_tree(self):
        tree = {"cmd": "printenv", "out": ["GEMINI_API_KEY=abc123def456"], "n": 3,
                "nested": {"t": ("TELEGRAM_BOT_TOKEN=1:x",)}}
        out = redact_tree(tree)
        assert "abc123def456" not in str(out) and out["n"] == 3
        assert "1:x" not in str(out) and isinstance(out["nested"]["t"], list)

    def test_name_set_is_a_superset_of_the_codex_deny_sets(self):
        # E6 Delta: everything the Codex lane scrubs from the child env (and
        # every canary sentinel name) must be redacted when it shows up in a
        # trace — two contracts, one name set.
        from src.runner.executors.codex_cli import (
            CANARY_SENTINEL_NAMES,
            DENIED_ENV_NAMES,
            DENIED_ENV_PREFIXES,
        )
        for name in set(DENIED_ENV_NAMES) | set(CANARY_SENTINEL_NAMES):
            assert redact(f"{name}=leakedvalue") == f"{name}={REDACTED}", name
        for prefix in DENIED_ENV_PREFIXES:
            assert redact(f"{prefix}THING=leakedvalue") == f"{prefix}THING={REDACTED}", prefix


# Review 2026-10-29: every probe string that got a credential past the first
# cut, pinned as (input, forbidden substring, what must survive). Future regex
# edits are regression-tested against the whole corpus.
BYPASS_CORPUS = [
    # truncated PEM in a 500-char preview — no END armour
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAFAKEFAKEFAKEFAKE\nzzzzFAKEzzzz... [900 more]",
     "MIIEowIBAAKCAQEAFAKEFAKEFAKEFAKE", "... [900 more]"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQ\nAAtzc2gtZWQyNTUxOQAAACDFAKEFAKE... [120 more]",
     "AAtzc2gtZWQyNTUxOQAAACDFAKEFAKE", "... [120 more]"),
    ("-----BEGIN PGP PRIVATE KEY BLOCK-----\nlQOYBFAKEFAKE\n-----END PGP PRIVATE KEY BLOCK-----",
     "lQOYBFAKEFAKE", None),
    # quoted mid-line value; JSON-escaped newline (list-shaped tool_result → json.dumps)
    ("run TELEGRAM_BOT_TOKEN='1234567890:AAzzFAKE' ./x", "1234567890:AAzzFAKE", "./x"),
    ('{"stdout": "HOME=/x\\nTELEGRAM_BOT_TOKEN=1234567890:AAzzFAKE\\nPATH=/bin"}', "1234567890:AAzzFAKE", "PATH=/bin"),
    ('GEMINI_API_KEY="AIzaFAKE1234567"', "AIzaFAKE1234567", "GEMINI_API_KEY="),
    ('FOO_TOKEN="abc def ghi"', "abc def", "FOO_TOKEN="),
    # lower-case names (pydantic repr of Settings)
    ("Settings(telegram_bot_token='1234567890:AAzzFAKE', database_url='postgresql+asyncpg://assistant:hunter2hunter2@h/db', web_auth_token='webFAKE123')",
     "1234567890:AAzzFAKE", "Settings("),
    ("Settings(database_url='postgresql+asyncpg://assistant:hunter2hunter2@h/db')", "hunter2hunter2", None),
    # the Telegram bot token inside a URL
    ("curl https://api.telegram.org/bot1234567890:AAzzFAKEFAKE/getMe", "1234567890:AAzzFAKEFAKE", "api.telegram.org/bot"),
    # Basic auth, curl -u, a bare DSN, ?token=, rclone secret_access_key
    ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA==", "Authorization: Basic"),
    ("curl -u admin:hunter2hunter2 https://x", "hunter2hunter2", "-u admin:"),
    ("psql postgres://assistant:hunter2hunter2@db:5432/x", "hunter2hunter2", "postgres://assistant:"),
    ("GET /api?token=zzzzFAKEzzzz&x=1", "zzzzFAKEzzzz", "GET /api?token="),
    ("secret_access_key = FAKEFAKEFAKE1234", "FAKEFAKEFAKE1234", "secret_access_key"),
    ("x-api-key: sk-FAKEFAKEFAKE1234", "sk-FAKEFAKEFAKE1234", "x-api-key"),
    # plutil / launchctl print shapes; tabs; ANSI colour between name and =
    ('    "GEMINI_API_KEY" => "AIzaFAKE1234567"', "AIzaFAKE1234567", "GEMINI_API_KEY"),
    ("\tGEMINI_API_KEY => AIzaFAKE1234567", "AIzaFAKE1234567", "GEMINI_API_KEY"),
    ("GEMINI_API_KEY\tAIzaFAKE1234567", "AIzaFAKE1234567", "GEMINI_API_KEY"),
    ("GEMINI_API_KEY\x1b[0m=AIzaFAKE1234567", "AIzaFAKE1234567", "GEMINI_API_KEY"),
]


class TestBypassCorpus:
    @pytest.mark.parametrize("text,forbidden,survives", BYPASS_CORPUS,
                             ids=[t[0][:28] for t in BYPASS_CORPUS])
    def test_corpus(self, text, forbidden, survives):
        out = redact(text)
        assert forbidden not in out, out
        assert REDACTED in out
        if survives:
            assert survives in out, out

    def test_token_counters_and_code_shapes_survive(self):
        # `token` joined the generic key list; the trailing `s` and `_count`
        # keep the ledger's own fields out of it.
        for text in ("input_tokens=15 output_tokens=9363", "max_tokens: 4096", "token_count: 12",
                     "cache_read_tokens=379675", "tokens=5", "the URL is https://example.com",
                     "https://github.com/Piserchia/ai-server.git", "API Error: 529 Overloaded.",
                     "X_URL_HELPER=1", "src/runner/executors/codex_cli.py:462"):
            assert redact(text) == text, text


def _assistant(*blocks) -> AssistantMessage:
    return AssistantMessage(content=list(blocks), model="claude-opus-5")


def _user_with_tool_result(text: str) -> UserMessage:
    return UserMessage(content=[ToolResultBlock(tool_use_id="t1", content=text, is_error=False)])


@pytest.fixture
def sinks(monkeypatch):
    from src.runner import session
    appended: list[tuple] = []
    published: list[dict] = []
    monkeypatch.setattr(session.audit_log, "append",
                        lambda job_id, kind, **f: appended.append((kind, f)))

    async def _pub(job_id, payload):
        published.append(payload)
    monkeypatch.setattr(session, "_publish_stream", _pub)
    return appended, published


class TestHandleMessage:
    async def test_tool_result_preview_never_lands_a_credential(self, sinks):
        """The gate: a printenv-shaped tool_result reaches neither sink raw."""
        from src.runner import session
        appended, published = sinks
        await session._handle_message("job1", _user_with_tool_result(PRINTENV), [])
        blob = repr(appended) + repr(published)
        for secret in SECRETS:
            assert secret not in blob, secret
        assert appended and appended[0][0] == "tool_result"
        assert f"GEMINI_API_KEY={REDACTED}" in appended[0][1]["result_preview"]

    async def test_text_is_redacted_in_both_sinks_but_not_in_the_summary(self, sinks):
        from src.runner import session
        appended, published = sinks
        chunks: list[str] = []
        leaky = "here it is: sk-ant-api03-WWWWWWWWWWWW"
        await session._handle_message("job1", _assistant(TextBlock(text=leaky)), chunks)
        assert "sk-ant-api03-WWWWWWWWWWWW" not in repr(appended)
        assert "sk-ant-api03-WWWWWWWWWWWW" not in repr(published)
        assert published and published[0]["kind"] == "text" and REDACTED in published[0]["text"]
        # final_text_chunks is deliberately NOT redacted: it becomes the job's
        # result and feeds the TASK_COMPLETE marker parser.
        assert chunks == [leaky]

    async def test_thinking_and_tool_use_input_are_redacted(self, sinks):
        from src.runner import session
        appended, published = sinks
        msg = _assistant(
            ThinkingBlock(thinking="remember GEMINI_API_KEY=abc123def456", signature="s"),
            ToolUseBlock(id="t1", name="Bash",
                         input={"command": "curl -H 'Authorization: Bearer sk-ant-api03-YYYYYYYYYYYY' https://x"}),
        )
        await session._handle_message("job1", msg, [])
        blob = repr(appended) + repr(published)
        assert "abc123def456" not in blob and "sk-ant-api03-YYYYYYYYYYYY" not in blob
        tool_use = next(f for k, f in appended if k == "tool_use")
        assert tool_use["tool_name"] == "Bash" and "curl -H" in tool_use["input"]["command"]

    async def test_redaction_runs_after_truncation(self, sinks):
        # The preview is cut to 500 chars FIRST, then redacted: the whole line
        # sits inside the kept part, and the cut marker's count is the raw
        # text's (redact-before-truncate would change it by len(REDACTED)-12).
        from src.runner import session
        appended, _ = sinks
        big = "x" * 400 + "\nGEMINI_API_KEY=abc123def456\n" + "y" * 600
        await session._handle_message("job1", _user_with_tool_result(big), [])
        preview = appended[0][1]["result_preview"]
        assert f"GEMINI_API_KEY={REDACTED}" in preview
        assert "abc123def456" not in preview
        assert preview.endswith(f"... [{len(big) - 500} more]")

    def test_derived_text_events_are_redacted_too(self):
        # Review 2026-10-29 #2: the marker parser's derived rows
        # (task_complete.summary, task_question.question, eval_fail.feedback …)
        # are built from the RAW final text and appended to the JSONL — they
        # pass through redact_tree before the append, after parsing.
        import inspect
        from src.runner import session
        from src.runner.session import extract_text_events
        events = extract_text_events("did it\nTASK_COMPLETE: set GEMINI_API_KEY=AIzaFAKE1234567 in .env")
        assert events and "AIzaFAKE1234567" in repr(events)           # parsing saw the raw text
        assert "AIzaFAKE1234567" not in repr([redact_tree(e) for e in events])
        src = inspect.getsource(session.run_session)
        assert "audit_log.append(job_id, kind, **secret_redact.redact_tree(evt))" in src


class TestCodexSink:
    async def test_codex_sink_redacts_before_append_and_stream(self, monkeypatch):
        from src.runner.executors import codex_cli
        audited: list[tuple] = []
        published: list[str] = []
        monkeypatch.setattr(codex_cli.audit_log, "append",
                            lambda job_id, kind, **fields: audited.append((kind, fields)))

        class FakeRedis:
            async def publish(self, channel, body):
                published.append(body)
        monkeypatch.setattr(codex_cli, "redis", FakeRedis())
        sink = codex_cli.default_sink("job1")
        await sink("tool_result", {"tool_use_id": "i1", "is_error": False, "exit_code": 0,
                                   "result_preview": PRINTENV, "output": PRINTENV})
        await sink("text", {"text": "token sk-ant-api03-VVVVVVVVVVVV"})
        blob = repr(audited) + "".join(published)
        for secret in SECRETS + ("sk-ant-api03-VVVVVVVVVVVV",):
            assert secret not in blob, secret
        assert audited[0][0] == "tool_result" and audited[0][1]["exit_code"] == 0
        assert f"GEMINI_API_KEY={REDACTED}" in audited[0][1]["result_preview"]
        assert json.loads(published[1])["kind"] == "text"

    def test_the_canary_sink_is_not_redacted(self):
        # The canary's own sink stays raw: check_canary reads the in-memory
        # events (not the JSONL), and its child env is an ALLOW-LIST so no real
        # credential can reach that log — redacting it buys nothing and would
        # blur the sentinel check.
        import inspect
        from src.runner.executors import codex_cli
        assert "redact_tree(" in inspect.getsource(codex_cli.default_sink)
        assert "redact" not in inspect.getsource(codex_cli.run_canary)
