# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
from pathlib import Path
from typing import TextIO

import httpx

from .chat_runtime import build_chat_messages, collect_stream, trailing_newline_delta
from .cli_http import REQUEST_HEADERS
from .services.model_providers import chat_stream


def resolve_prompt_file(prompt_ref: str, cwd: Path | None = None) -> Path:
    base_dir = cwd or Path.cwd()
    prompt_path = Path(prompt_ref).expanduser()

    candidates: list[Path]
    if prompt_path.is_absolute():
        candidates = [prompt_path]
    elif prompt_path.parent == Path("."):
        candidates = [base_dir / "prompts" / prompt_path.name, base_dir / prompt_path]
    else:
        candidates = [base_dir / prompt_path]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = ", ".join(str(candidate) for candidate in candidates)
    raise ValueError(f"Prompt file not found: {prompt_ref} (searched: {searched})")


def load_prompt(prompt_ref: str, cwd: Path | None = None) -> str:
    prompt_file = resolve_prompt_file(prompt_ref, cwd)
    content = prompt_file.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Prompt file is empty: {prompt_file}")
    return content


def build_messages(question: str, prompt: str | None = None) -> list[dict[str, str]]:
    return build_chat_messages(question, prompt)


def run_batch_command(
    question: str,
    model: str,
    prompt_ref: str | None = None,
    session_id: int | None = None,
    user: str = "default",
    stdout: TextIO | None = None,
    cwd: Path | None = None,
) -> int:
    output = stdout
    if output is None:
        import sys

        output = sys.stdout

    if session_id is not None:
        from .config import DATABASE
        from .database import get_session_for_user

        if get_session_for_user(DATABASE, session_id, user) is None:
            raise ValueError(f"Session {session_id} not found for user {user!r}")

    prompt = load_prompt(prompt_ref, cwd) if prompt_ref else None
    messages = build_messages(question, prompt)
    full_response = ""
    for token, full_response in collect_stream(chat_stream(messages, model)):
        output.write(token)
        output.flush()
    final_delta = trailing_newline_delta(full_response)
    if final_delta:
        output.write(final_delta)
        output.flush()

    if session_id is not None and full_response:
        from .database import add_message, get_messages
        add_message(DATABASE, session_id, "user", question)
        add_message(DATABASE, session_id, "assistant", full_response)
        existing = get_messages(DATABASE, session_id)
        if len(existing) <= 2:
            from .database import update_session_title_for_user
            title = question[:60] + ("..." if len(question) > 60 else "")
            update_session_title_for_user(DATABASE, session_id, user, title)

    return 0


def run_server_batch_command(
    question: str,
    model: str,
    base_url: str,
    prompt_ref: str | None = None,
    session_id: int | None = None,
    user: str = "default",
    stdout: TextIO | None = None,
    cwd: Path | None = None,
    search: bool = False,
) -> int:
    output = stdout
    if output is None:
        import sys

        output = sys.stdout

    prompt = load_prompt(prompt_ref, cwd) if prompt_ref else None
    body = {"message": question, "model": model}
    if prompt is not None:
        body["system_prompt"] = prompt
    if session_id is not None:
        body["session_id"] = session_id
        body["user"] = user
    if search:
        body["search"] = True

    with httpx.Client(timeout=httpx.Timeout(300, connect=10)) as client:
        with client.stream(
            "POST", f"{base_url}/api/batch", json=body, headers=REQUEST_HEADERS
        ) as resp:
            resp.raise_for_status()
            full_response = ""
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                if chunk.get("done"):
                    break
                token = chunk.get("token", "")
                if token:
                    full_response = f"{full_response}{token}"
                    output.write(token)
                    output.flush()
            final_delta = trailing_newline_delta(full_response)
            if final_delta:
                output.write(final_delta)
                output.flush()
    return 0
