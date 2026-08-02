# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
"""Shared helpers for LLMFlask workbench modules."""

from pathlib import Path


def strip_code_fences(text: str) -> str:
    """Remove ``` fences from LLM response to get raw code."""
    lines = text.strip().split('\n')
    if lines and lines[0].strip().startswith('```'):
        lines = lines[1:]
    if lines and lines[-1].strip().rstrip().endswith('```'):
        lines = lines[:-1]
    return '\n'.join(lines)


def load_prompt_file(name: str) -> str:
    """Load a prompt file from cwd/prompts/ or parent-dir/prompts/."""
    candidates = [
        Path.cwd() / "prompts" / name,
        Path(__file__).resolve().parents[3] / "prompts" / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt file not found: {name}")
