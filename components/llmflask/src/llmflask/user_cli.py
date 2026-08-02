# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import sys
from urllib.parse import quote

from .cli_http import api_request


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _run_user_command(args, host: str, port: int) -> int:
    base = _base_url(host, port)
    handlers = {
        "list":   lambda: _user_list(base),
        "add":    lambda: _user_add(base, args.name),
        "rename": lambda: _user_rename(base, getattr(args, 'old', ''), getattr(args, 'new', '')),
        "remove": lambda: _user_remove(base, args.name),
    }
    handler = handlers.get(args.user_action)
    if handler:
        return handler()
    print("llmflask: error: Use: user list | add | rename | remove", file=sys.stderr)
    return 1


def _user_list(base: str) -> int:
    resp = api_request(base, "GET", "/api/users")
    if resp is None:
        return 1
    users = resp.json()
    for u in users:
        print(f"  {u.get('name', '?'):<20} {u.get('chats', 0)} chats")
    return 0


def _user_add(base: str, name: str) -> int:
    resp = api_request(base, "POST", "/api/users", json={"name": name})
    if resp is None:
        return 1
    print(f"User created: {name}")
    return 0


def _user_rename(base: str, old: str, new: str) -> int:
    resp = api_request(base, "PUT", f"/api/users/{quote(old, safe='')}", json={"name": new})
    if resp is None:
        return 1
    print(f"User renamed: {old} -> {new}")
    return 0


def _user_remove(base: str, name: str) -> int:
    resp = api_request(base, "DELETE", f"/api/users/{quote(name, safe='')}")
    if resp is None:
        return 1
    print(f"User deleted: {name}")
    return 0
