# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json


def test_ollama_reachable_true_when_api_responds(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    class MockResponse:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda *a, **k: MockResponse())

    assert model_providers.ollama_reachable() is True


def test_ollama_reachable_false_on_error(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    def raise_error(*a, **k):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "get", raise_error)

    assert model_providers.ollama_reachable() is False


def test_list_models_combines_enabled_providers(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    monkeypatch.setattr(
        model_providers,
        "load_api_keys",
        lambda: {"OPENAI_API_KEY": "openai-key", "DEEPSEEK_API_KEY": "deepseek-key"},
    )

    class MockResponse:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data

    def mock_get(url, **kwargs):
        if url.endswith("/api/tags"):
            return MockResponse({"models": [{"name": "llama3.1:8b"}]})
        if url == "https://api.openai.com/v1/models":
            return MockResponse({"data": [{"id": "gpt-4.1-mini"}]})
        if url == "https://api.deepseek.com/models":
            return MockResponse({"data": [{"id": "deepseek-v4-flash"}]})
        raise AssertionError(url)

    monkeypatch.setattr(httpx, "get", mock_get)

    models = model_providers.list_models()

    assert [m["name"] for m in models] == [
        "ollama/llama3.1:8b",
        "openai/gpt-4.1-mini",
        "deepseek/deepseek-v4-flash",
    ]
    assert models[0]["label"] == "Ollama: llama3.1:8b"


def test_list_models_skips_remote_without_keys(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    monkeypatch.setattr(model_providers, "load_api_keys", lambda: {})

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"models": []}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: MockResponse())

    assert model_providers.list_models() == []


def test_chat_stream_routes_legacy_model_to_ollama(monkeypatch):
    from llmflask.services import model_providers

    seen = {}

    def fake_ollama(messages, model):
        seen["model"] = model
        yield "ok"

    monkeypatch.setattr(model_providers, "ollama_chat_stream", fake_ollama)

    assert list(model_providers.chat_stream([{"role": "user", "content": "hi"}], "llama3")) == ["ok"]
    assert seen["model"] == "llama3"


def test_ollama_chat_stream_forwards_messages_and_context_option(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    captured = {}

    class MockResponse:
        def raise_for_status(self):
            pass

        def iter_lines(self):
            return iter([
                json.dumps({"message": {"content": "ok"}}),
                json.dumps({"done": True}),
            ])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_stream(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return MockResponse()

    monkeypatch.setattr(httpx, "stream", mock_stream)
    messages = [{"role": "user", "content": "question\n\nsearch context"}]

    assert list(model_providers.ollama_chat_stream(messages, "qwen3:4b")) == ["ok"]
    assert captured == {
        "method": "POST",
        "url": f"{model_providers.OLLAMA_URL}/api/chat",
        "json": {
            "model": "qwen3:4b",
            "messages": messages,
            "stream": True,
            "options": {"num_ctx": model_providers.NUM_CTX},
        },
        "timeout": 300,
    }


def test_openai_compatible_chat_stream_yields_sse_tokens(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
        "data: " + json.dumps({"choices": [{"delta": {"content": " World"}}]}),
        "data: [DONE]",
    ]
    captured = {}

    class MockResponse:
        def raise_for_status(self):
            pass
        def iter_lines(self):
            return iter(lines)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def mock_stream(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return MockResponse()

    monkeypatch.setattr(httpx, "stream", mock_stream)

    provider = model_providers.REMOTE_PROVIDERS["openai"]
    tokens = list(
        model_providers.openai_compatible_chat_stream(
            [{"role": "user", "content": "hi"}],
            "gpt-test",
            provider,
            "secret",
        )
    )

    assert tokens == ["Hello", " World"]
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["json"]["stream"] is True
    assert captured["headers"]["Authorization"] == "Bearer secret"


def test_chat_stream_requires_remote_api_key(monkeypatch):
    import pytest
    from llmflask.services import model_providers

    monkeypatch.setattr(model_providers, "load_api_keys", lambda: {})

    with pytest.raises(RuntimeError, match="API key"):
        list(model_providers.chat_stream([], "openai/gpt-test"))


def test_providers_defaults_include_expected_entries():
    from llmflask.services import model_providers

    providers = model_providers.REMOTE_PROVIDERS
    assert "openai" in providers
    assert "deepseek" in providers
    assert "zen" in providers
    assert providers["zen"].base_url == "https://opencode.ai/zen/v1"
    assert providers["zen"].label == "OpenCode Zen"


def test_user_providers_json_overrides_defaults(monkeypatch, tmp_path):
    from llmflask.services import model_providers

    user_json = tmp_path / "providers.json"
    user_json.write_text('''{
      "providers": [
        {"name": "custom", "label": "Custom", "base_url": "https://custom.ai/v1", "api_key_name": "CUSTOM_API_KEY"}
      ]
    }''')

    monkeypatch.setattr(model_providers, "_user_providers_path", lambda: user_json)

    providers = model_providers._load_providers()
    assert "custom" in providers
    assert "openai" not in providers


def test_user_providers_invalid_json_warns_and_uses_bundled_defaults(
    monkeypatch, tmp_path, capsys
):
    from llmflask.services import model_providers

    user_json = tmp_path / "providers.json"
    user_json.write_text("{not valid json")

    monkeypatch.setattr(model_providers, "_user_providers_path", lambda: user_json)

    providers = model_providers._load_providers()
    assert "openai" in providers
    assert "deepseek" in providers
    assert "zen" in providers
    assert "invalid providers file" in capsys.readouterr().err


def test_user_providers_path_honors_xdg_config_home(monkeypatch, tmp_path):
    from llmflask.services import model_providers

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    assert model_providers._user_providers_path() == (
        tmp_path / "config" / "llmflask" / "providers.json"
    )


def test_user_provider_rejects_unsupported_api_style(
    monkeypatch, tmp_path, capsys
):
    from llmflask.services import model_providers

    user_json = tmp_path / "providers.json"
    user_json.write_text(
        '''{"providers": [{"name": "custom", "label": "Custom", "base_url": "https://custom.invalid", "api_style": "other"}]}''',
        encoding="utf-8",
    )
    monkeypatch.setattr(model_providers, "_user_providers_path", lambda: user_json)

    providers = model_providers._load_providers()

    assert "custom" not in providers
    assert "openai" in providers
    assert "invalid providers file" in capsys.readouterr().err


def test_zen_provider_models_listed_with_key(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    monkeypatch.setattr(
        model_providers,
        "load_api_keys",
        lambda: {"ZEN_API_KEY": "zen-key"},
    )

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [{"id": "big-pickle"}, {"id": "mimo-v2.5-free"}]}

    def mock_get(url, **kwargs):
        if url.endswith("/api/tags"):
            return MockResponse()
        if url == "https://opencode.ai/zen/v1/models":
            return MockResponse()
        return MockResponse()

    monkeypatch.setattr(httpx, "get", mock_get)

    models = model_providers.list_models()
    zen_models = [m for m in models if m["provider"] == "zen"]
    assert len(zen_models) == 2
    assert zen_models[0]["name"] == "zen/big-pickle"
    assert zen_models[1]["name"] == "zen/mimo-v2.5-free"


def test_zen_models_listed_without_key(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    monkeypatch.setattr(
        model_providers,
        "load_api_keys",
        lambda: {},
    )

    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"data": [{"id": "big-pickle"}]}

    def mock_get(url, **kwargs):
        if url.endswith("/api/tags"):
            return MockResponse()
        if url == "https://opencode.ai/zen/v1/models":
            return MockResponse()
        return MockResponse()

    monkeypatch.setattr(httpx, "get", mock_get)

    models = model_providers.list_models()
    zen_models = [m for m in models if m["provider"] == "zen"]
    assert len(zen_models) == 1
    assert zen_models[0]["name"] == "zen/big-pickle"


def test_zen_requires_auth_is_false():
    from llmflask.services import model_providers

    provider = model_providers.REMOTE_PROVIDERS["zen"]
    assert provider.requires_auth is False
    assert provider.api_key_name == "ZEN_API_KEY"


def test_openai_requires_auth_still_true():
    from llmflask.services import model_providers

    provider = model_providers.REMOTE_PROVIDERS["openai"]
    assert provider.requires_auth is True


def test_remote_headers_omits_auth_without_key():
    from llmflask.services.model_providers import _remote_headers

    headers = _remote_headers("")
    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/json"

    headers_with_key = _remote_headers("secret")
    assert headers_with_key["Authorization"] == "Bearer secret"


def test_zen_chat_stream_works_without_key(monkeypatch):
    import httpx
    from llmflask.services import model_providers

    monkeypatch.setattr(model_providers, "load_api_keys", lambda: {})

    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
        "data: [DONE]",
    ]

    class MockResponse:
        def raise_for_status(self):
            pass
        def iter_lines(self):
            return iter(lines)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: MockResponse())

    tokens = list(model_providers.chat_stream(
        [{"role": "user", "content": "hi"}], "zen/big-pickle"
    ))
    assert tokens == ["Hello"]


def test_openai_chat_stream_still_requires_key(monkeypatch):
    import pytest
    from llmflask.services import model_providers

    monkeypatch.setattr(model_providers, "load_api_keys", lambda: {})

    with pytest.raises(RuntimeError, match="API key"):
        list(model_providers.chat_stream([], "openai/gpt-test"))
