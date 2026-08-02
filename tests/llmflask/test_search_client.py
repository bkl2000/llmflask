# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
def test_search_returns_results(monkeypatch):
    import httpx
    from llmflask.services.search_client import search

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"results": [
                {"title": "Test", "content": "Snippet", "url": "http://x.com"}
            ]}

    calls = []
    def mock_get(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return MockResponse()

    monkeypatch.setattr(httpx, "get", mock_get)
    results = search("test")
    assert len(results) == 1
    assert results[0]["title"] == "Test"
    assert len(calls) == 1
    assert calls[0]["kwargs"]["params"]["time_range"] == "day"


def test_search_custom_time_range(monkeypatch):
    import httpx
    from llmflask.services.search_client import search

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"results": []}

    calls = []
    def mock_get(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return MockResponse()

    monkeypatch.setattr(httpx, "get", mock_get)
    search("test", time_range="week")
    assert calls[0]["kwargs"]["params"]["time_range"] == "week"


def test_search_handles_error(monkeypatch):
    import httpx
    from llmflask.services.search_client import search

    def mock_get(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", mock_get)
    assert search("test") == []


def test_format_results():
    from llmflask.services.search_client import format_results

    results = [
        {"title": "Result 1", "content": "Snippet 1", "url": "http://1.com"},
        {"title": "Result 2", "content": "Snippet 2", "url": "http://2.com"},
    ]
    formatted = format_results(results)
    assert "## Web Search Results (" in formatted
    assert "Result 1" in formatted
    assert "Snippet 1" in formatted
    assert "http://1.com" in formatted


def test_format_results_includes_date():
    from llmflask.services.search_client import format_results
    from datetime import datetime

    results = [{"title": "T", "content": "S", "url": "http://x.com"}]
    formatted = format_results(results)
    today = datetime.now().strftime("%Y-%m-%d")
    assert f"## Web Search Results ({today})" in formatted


def test_format_results_empty():
    from llmflask.services.search_client import format_results
    assert format_results([]) == ""
