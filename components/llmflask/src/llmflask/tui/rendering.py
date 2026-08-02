# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import curses
import textwrap


def _wrap_text(text: str, width: int) -> list[str]:
    if width <= 0:
        return [""]
    result = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            result.append("")
        else:
            result.extend(textwrap.wrap(paragraph, width=width))
    return result or [""]


def _render_md_line(line: str) -> tuple[int, str]:
    """Returns (curses_attr, rendered_text) for a single line."""
    stripped = line.strip()
    if not stripped:
        return curses.A_NORMAL, ""

    # Code blocks (backtick)
    if stripped.startswith("```"):
        return curses.A_DIM, stripped

    # Headings
    if stripped.startswith("### ") or stripped.startswith("## ") or stripped.startswith("# "):
        return curses.A_BOLD, stripped

    # Bold markers: remove ** and apply bold
    attr = curses.A_NORMAL
    if "**" in stripped:
        attr = curses.A_BOLD
        stripped = stripped.replace("**", "")

    # List items
    if stripped.startswith("- ") or stripped.startswith("* "):
        attr = curses.A_NORMAL
        stripped = "  " + stripped

    # Blockquote
    if stripped.startswith("> "):
        attr = curses.A_NORMAL

    # Horizontal rule
    if set(stripped) <= {"-", " ", ""} and len(stripped) >= 3:
        return curses.A_NORMAL, "─" * 40

    return attr, stripped


def _is_indented_code_line(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


def _render_message_lines(content: str, width: int) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    in_code_block = False

    for raw_line in content.split("\n"):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            lines.append((curses.A_DIM, stripped))
            continue

        if in_code_block or _is_indented_code_line(raw_line):
            lines.append((curses.A_DIM, raw_line))
            continue

        for wrapped_line in _wrap_text(raw_line, width):
            lines.append(_render_md_line(wrapped_line))

    return lines or [(curses.A_NORMAL, "")]
