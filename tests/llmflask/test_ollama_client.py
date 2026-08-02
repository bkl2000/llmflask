# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
def test_list_models_returns_list(monkeypatch):
    import httpx
    from llmflask.services.ollama_client import list_models

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"models": [{"name": "llama3.1:8b"}, {"name": "qwen3:14b"}]}

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx, "get", mock_get)
    models = list_models()
    assert len(models) == 2
    assert models[0]["name"] == "llama3.1:8b"


def test_list_models_handles_error(monkeypatch):
    import httpx
    from llmflask.services.ollama_client import list_models

    def mock_get(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", mock_get)
    models = list_models()
    assert models == []


def test_chat_stream_yields_tokens(monkeypatch):
    from llmflask.services.ollama_client import chat_stream

    import json

    lines = [
        json.dumps({"message": {"content": "Hello"}, "done": False}),
        json.dumps({"message": {"content": " World"}, "done": False}),
        json.dumps({"message": {"content": ""}, "done": True}),
    ]

    class MockResponse:
        def __init__(self):
            self.status_code = 200
        def raise_for_status(self):
            pass
        def iter_lines(self):
            return iter(lines)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    class MockClient:
        def stream(self, *args, **kwargs):
            return MockResponse()

    monkeypatch.setattr("llmflask.services.ollama_client.httpx.stream", MockClient().stream)
    tokens = list(chat_stream([{"role": "user", "content": "hi"}], "llama3.1:8b"))
    assert tokens == ["Hello", " World"]


def test_chat_stream_includes_num_ctx(monkeypatch):
    from llmflask.services.ollama_client import chat_stream

    import json

    lines = [json.dumps({"message": {"content": ""}, "done": True})]

    class MockResponse:
        def __init__(self):
            self.status_code = 200
        def raise_for_status(self):
            pass
        def iter_lines(self):
            return iter(lines)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    captured_body = {}

    class MockClient:
        def stream(self, method, url, json=None, **kwargs):
            captured_body.update(json or {})
            return MockResponse()

    monkeypatch.setattr("llmflask.services.ollama_client.httpx.stream", MockClient().stream)
    list(chat_stream([{"role": "user", "content": "hi"}], "qwen3:14b"))
    assert "options" in captured_body
    assert captured_body["options"]["num_ctx"] == 8192
