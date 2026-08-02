# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
def ensure_trailing_newline(text: str) -> str:
    if not text or text.endswith("\n"):
        return text
    return f"{text}\n"
