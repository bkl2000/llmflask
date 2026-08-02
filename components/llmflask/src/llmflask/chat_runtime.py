# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from collections.abc import Iterable, Iterator

from .text_utils import ensure_trailing_newline


def build_chat_messages(question: str, system_prompt: str | None = None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt is not None:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})
    return messages


def trailing_newline_delta(text: str) -> str:
    normalized = ensure_trailing_newline(text)
    return normalized[len(text):]


def collect_stream(tokens: Iterable[str]) -> Iterator[tuple[str, str]]:
    full_response = ""
    for token in tokens:
        full_response += token
        yield token, full_response
