# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from pathlib import Path

from ..chat_runtime import build_chat_messages
from ..services.model_providers import chat_stream
from ._utils import load_prompt_file, strip_code_fences


def _fill_repair_prompt(
    template: str,
    error_output: str,
    script_path: str,
    script_content: str,
) -> str:
    return (
        template
        .replace("{{error_output}}", error_output)
        .replace("{{script_path}}", script_path)
        .replace("{{script_content}}", script_content)
    )


def attempt_repair(
    pool_path: str,
    script_path: str,
    error_output: str,
    model_ref: str,
) -> str | None:
    pool_dir = Path(pool_path).expanduser().resolve()
    script_file = pool_dir / script_path

    if not script_file.is_file():
        return None

    script_content = script_file.read_text(encoding="utf-8")
    template = load_prompt_file("pool_repair.md")
    prompt = _fill_repair_prompt(template, error_output, script_path, script_content)
    messages = build_chat_messages(prompt)

    response = ""
    for token in chat_stream(messages, model_ref):
        response += token

    fixed = response.strip()
    fixed = strip_code_fences(fixed)
    stripped_original = strip_code_fences(script_content).strip()
    if not fixed or fixed == stripped_original:
        return None

    return fixed
