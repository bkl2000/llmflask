# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import httpx
from datetime import datetime
from ..config import SEARXNG_URL


def search(query: str, time_range: str = "day") -> list[dict]:
    try:
        resp = httpx.get(
            f"{SEARXNG_URL}/search",
            params={"q": query, "format": "json", "time_range": time_range},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])[:5]
    except Exception:
        return []


def format_results(results: list[dict]) -> str:
    if not results:
        return ""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"\nCurrent date: {today}.\n"
        "The following web search results are current.\n"
        "For current facts, prefer these search results over training knowledge.\n"
        "\n## Web Search Results\n"
    ]
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        snippet = r.get("content", "") or r.get("snippet", "")
        url = r.get("url", "")
        lines.append(f"{i}. **{title}**\n   {snippet}\n   {url}\n")
    return "\n".join(lines)
