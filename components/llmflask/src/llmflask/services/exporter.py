# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import subprocess
from datetime import datetime


def _messages_as_md(messages: list[dict], title: str = "Chat") -> str:
    lines = [f"# Chat: \"{title}\"\n"]
    for i, m in enumerate(messages, 1):
        role = m["role"].capitalize()
        ts = m.get("created_at", "")
        if ts:
            ts = datetime.fromisoformat(ts).strftime("%d.%m.%Y %H:%M")
        lines.append(f"## {i}. {role} - {ts}\n")
        lines.append(m["content"].strip())
        lines.append("")
    return "\n".join(lines)


def export_md(messages: list[dict], title: str = "Chat") -> str:
    return _messages_as_md(messages, title)


def export_pdf(messages: list[dict], title: str = "Chat", filename: str = "") -> bytes:
    md = _messages_as_md(messages, title)
    cmd = ["pandoc", "-f", "markdown", "-t", "pdf", "--pdf-engine=weasyprint"]
    if filename:
        cmd.extend(["-o", filename])
    else:
        cmd.extend(["-o", "-"])
    try:
        result = subprocess.run(
            cmd,
            input=md.encode(),
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "pandoc is not installed. Install it with: sudo apt install pandoc"
        ) from None
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode() if result.stderr else "pandoc failed")
    if filename:
        return b""
    return result.stdout


def export_ipynb(messages: list[dict], title: str = "Chat") -> str:
    if not messages:
        notebook = {
            "cells": [],
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.12.0"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        return json.dumps(notebook, indent=1, ensure_ascii=False)

    md = _messages_as_md(messages, title)
    cells = []
    sections = md.split("\n## ")
    first = sections[0]
    if first.startswith("# "):
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [first],
        })
    for sec in sections:
        if sec.startswith("# "):
            continue
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## " + sec],
        })
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12.0"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(notebook, indent=1, ensure_ascii=False)
