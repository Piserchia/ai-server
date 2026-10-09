#!/usr/bin/env python3
"""pickem-chart helper: the four calls the skill is allowed to make.

Stdlib only. Reads PICKEM_ADMIN_TOKEN from the production pickem .env itself
and sends it as X-Admin-Token -- the token never passes through the model's
context, a shell variable, or stdout. Prints the response body; exits 0 on a
2xx, 1 otherwise (and 2 on a usage error).

    chart_api.py get <request_id>
    chart_api.py stats <request_id>
    chart_api.py preview <request_id> --sql-file F
    chart_api.py complete <request_id> --spec-file F --model M
    chart_api.py fail <request_id> --message-file F
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("PICKEM_BASE_URL", "http://localhost:8793")
_DESCRIPTION = re.compile(r"^\s*pickem-chart request=(\d+)\s*$")


def parse_description(text: str) -> int | None:
    m = _DESCRIPTION.match(text or "")
    return int(m.group(1)) if m else None


def _env_path() -> str:
    root = os.environ.get("SERVER_ROOT") or os.path.expanduser("~/Library/Application Support/ai-server")
    return os.path.join(root, "projects", "pickem", ".env")


def read_admin_token(env_path: str) -> str:
    try:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("PICKEM_ADMIN_TOKEN="):
                    value = line.split("=", 1)[1].strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                        value = value[1:-1]
                    if value:
                        return value
    except OSError:
        pass
    print(f"FATAL: no PICKEM_ADMIN_TOKEN in {env_path}", file=sys.stderr)
    raise SystemExit(2)


def build(cmd, request_id, *, sql=None, spec=None, model=None, message=None, player_id=None):
    base = f"/api/internal/chart-requests/{request_id}"
    if cmd == "get":
        return "GET", base, None
    if cmd == "stats":
        return "GET", f"/api/players/{player_id}", None
    if cmd == "preview":
        return "POST", f"{base}/preview", json.dumps({"sql": sql}).encode()
    if cmd == "complete":
        return "POST", f"{base}/complete", json.dumps({"spec": spec, "model": model}).encode()
    if cmd == "fail":
        return "POST", f"{base}/fail", json.dumps({"message": message}).encode()
    raise ValueError(cmd)


def _call(method, path, body, token):
    req = urllib.request.Request(
        BASE + path, data=body, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json", "X-Admin-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()
    except urllib.error.URLError as exc:
        return 0, json.dumps({"detail": f"pickem service unreachable: {exc.reason}"})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["get", "stats", "preview", "complete", "fail"])
    ap.add_argument("request_id", type=int)
    ap.add_argument("--sql-file")
    ap.add_argument("--spec-file")
    ap.add_argument("--message-file")
    ap.add_argument("--model")
    a = ap.parse_args(argv)
    token = read_admin_token(_env_path())

    def read(path, what):
        if not path:
            ap.error(f"--{what}-file is required for {a.cmd}")
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    kwargs = {}
    if a.cmd == "stats":
        status, text = _call(*build("get", a.request_id), token)
        if status != 200:
            print(text)
            return 1
        kwargs["player_id"] = json.loads(text)["player_id"]
    elif a.cmd == "preview":
        kwargs["sql"] = read(a.sql_file, "sql")
    elif a.cmd == "complete":
        if not a.model:
            ap.error("--model is required for complete")
        kwargs["spec"] = json.loads(read(a.spec_file, "spec"))
        kwargs["model"] = a.model
    elif a.cmd == "fail":
        kwargs["message"] = read(a.message_file, "message").strip()

    status, text = _call(*build(a.cmd, a.request_id, **kwargs), token)
    print(status, text)
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
