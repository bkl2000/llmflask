# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import sys
from urllib.parse import quote

from .cli_http import api_request


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _run_session_command(args, host: str, port: int) -> int:
    base = _base_url(host, port)
    user = getattr(args, "user", "default")
    handlers = {
        "list":   lambda: _session_list(base, user),
        "remove": lambda: _session_remove(base, args.name, user),
    }
    handler = handlers.get(args.session_action)
    if handler:
        return handler()
    print("llmflask: error: Use: session list | remove <id> | remove all", file=sys.stderr)
    return 1


def _session_list(base: str, user: str = "default") -> int:
    resp = api_request(base, "GET", "/api/sessions", params={"user": user})
    if resp is None:
        return 1
    sessions = resp.json()
    if not sessions:
        print("No sessions.")
        return 0
    print(f"{'ID':<6} {'TITLE':<40} {'MODEL':<25}")
    for s in sessions:
        print(f"{s.get('id',''):<6} {s.get('title','')[:38]:<40} {s.get('model','')[:23]:<25}")
    return 0


def _session_remove(base: str, name: str | None, user: str = "default") -> int:
    if name == "all":
        resp = api_request(base, "GET", "/api/sessions", params={"user": user})
        if resp is None:
            return 1
        sessions = resp.json()
        count = 0
        failed = False
        for s in sessions:
            if api_request(base, "DELETE", f"/api/sessions/{s['id']}", params={"user": user}):
                count += 1
            else:
                failed = True
        print(f"Deleted {count} session{'s' if count != 1 else ''}.")
        return 1 if failed else 0
    resp = api_request(base, "DELETE", f"/api/sessions/{name}", params={"user": user})
    if resp is None:
        return 1
    print(f"Deleted session: {name}")
    return 0
