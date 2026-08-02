# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json

import httpx

from ..config import NUM_CTX, OLLAMA_URL
from .model_providers import list_ollama_models


def list_models() -> list[dict]:
    models = []
    for model in list_ollama_models():
        entry = dict(model)
        entry["name"] = entry.get("id", entry.get("name", ""))
        models.append(entry)
    return models


def chat_stream(messages: list[dict], model: str):
    body = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"num_ctx": NUM_CTX},
    }
    try:
        with httpx.stream(
            "POST",
            f"{OLLAMA_URL}/api/chat",
            json=body,
            timeout=300,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("done"):
                    break
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
    except Exception:
        yield ""
