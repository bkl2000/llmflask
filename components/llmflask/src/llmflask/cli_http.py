# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
"""Shared HTTP helpers for the LLMFlask CLI."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator

import httpx


def api_request(base: str, method: str, path: str, **kwargs) -> httpx.Response | None:
    try:
        resp = httpx.request(method, f"{base}{path}", timeout=kwargs.pop("timeout", 10), **kwargs)
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("error")
        except Exception:
            detail = None
        message = detail or e.response.reason_phrase or "request failed"
        print(f"llmflask: error: {e.response.status_code} {message}", file=sys.stderr)
        return None
    except httpx.ConnectError:
        print(f"llmflask: error: No server at {base}.", file=sys.stderr)
        return None
    except Exception as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return None


def iter_pool_events(resp: httpx.Response) -> Iterator[dict[str, object]]:
    for line in resp.iter_lines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        yield event
