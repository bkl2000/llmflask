# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import pytest
from llmflask.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("llmflask.config.DATABASE", db_path)
    app = create_app()
    app.config["DB_PATH"] = db_path
    with app.app_context():
        from llmflask.database import init_db
        init_db(db_path)
    with app.test_client() as c:
        c.environ_base["HTTP_X_LLMFLASK_REQUEST"] = "1"
        yield c


def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data


def test_get_models(client):
    resp = client.get("/api/models")
    assert resp.status_code == 200


def test_model_selection_returns_groups_and_key_hint(client, monkeypatch):
    from llmflask.services import model_providers as providers

    monkeypatch.setattr(providers, "load_api_keys", lambda: {})
    monkeypatch.setattr(providers, "list_models", lambda: [providers._model_entry("ollama", "qwen3:14b", "Ollama")])

    selection = client.get("/api/model-selection").get_json()

    assert [group["label"] for group in selection["groups"]] == ["Local", "Free", "API"]
    assert selection["models"][0]["name"] == "ollama/qwen3:14b"
    assert selection["models"][0]["group"] == "local"
    assert len(selection["models"]) == 1
    assert selection["default_model"] == "ollama/qwen3:14b"
    assert "llmflask --configure-api-keys" in selection["free_hint"]


def test_model_selection_does_not_default_to_paid_api(client, monkeypatch):
    from llmflask import cli
    from llmflask.services import model_providers as providers

    monkeypatch.setattr(providers, "load_api_keys", lambda: {"DEEPSEEK_API_KEY": "configured"})
    monkeypatch.setattr(providers, "list_models", lambda: [
        providers._model_entry("deepseek", "deepseek-chat", "DeepSeek")
    ])

    selection = client.get("/api/model-selection").get_json()

    assert selection["models"][0]["name"] == "deepseek/deepseek-chat"
    assert selection["default_model"] == ""
    monkeypatch.setattr(cli, "_api_get", lambda *args: selection)
    state = cli.TuiState("127.0.0.1", 5000)
    state.current_model = "ollama/missing"
    cli._load_models(state)
    assert state.current_model == ""


def test_create_and_list_sessions(client):
    resp = client.post("/api/sessions?user=test", json={"title": "Test", "model": "llama3.1:8b"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Test"

    resp = client.get("/api/sessions?user=test")
    assert resp.status_code == 200
    sessions = resp.get_json()
    assert len(sessions) == 1


def test_chat_requires_fields(client):
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 400


def test_batch_requires_fields(client):
    resp = client.post("/api/batch", json={})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "message and model required"


def test_batch_streams_without_prompt(client, monkeypatch):
    captured = {}

    def fake_chat_stream(history, model):
        captured["history"] = history
        captured["model"] = model
        yield "Hel"
        yield "lo"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/batch", json={"message": "Frage", "model": "qwen3:14b"})

    assert resp.status_code == 200
    assert b'"token": "Hel"' in resp.data
    assert b'"token": "lo"' in resp.data
    assert b'"token": "\\n"' in resp.data
    assert b'"done": true' in resp.data
    assert captured == {"history": [{"role": "user", "content": "Frage"}], "model": "qwen3:14b"}


def test_batch_logs_session_persistence_failure_without_losing_answer(
    client, monkeypatch, caplog
):
    def fake_chat_stream(history, model):
        yield "answer"

    session = client.post(
        "/api/sessions?user=alice",
        json={"title": "Test", "model": "qwen3:14b"},
    ).get_json()

    def fail_to_add_message(db_path, session_id, role, content):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)
    monkeypatch.setattr("llmflask.routes.chat.add_message", fail_to_add_message)

    with caplog.at_level("ERROR"):
        resp = client.post(
            "/api/batch",
            json={
                "message": "Frage",
                "model": "qwen3:14b",
                "session_id": session["id"],
                "user": "alice",
            },
        )
        body = resp.data

    assert resp.status_code == 200
    assert b'"token": "answer"' in body
    assert b'"done": true' in body
    assert f"Could not persist batch response for session {session['id']} and user alice" in caplog.text


def test_batch_rejects_session_owned_by_another_user_before_streaming(client, monkeypatch):
    session = client.post(
        "/api/sessions?user=alice",
        json={"title": "Private", "model": "qwen3:14b"},
    ).get_json()
    called = False

    def fake_chat_stream(history, model):
        nonlocal called
        called = True
        yield "answer"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)
    response = client.post(
        "/api/batch",
        json={
            "message": "Frage",
            "model": "qwen3:14b",
            "session_id": session["id"],
            "user": "bob",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "session not found"}
    assert called is False


def test_batch_does_not_duplicate_final_newline(client, monkeypatch):
    def fake_chat_stream(history, model):
        yield "ok\n"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/batch", json={"message": "Frage", "model": "qwen3:14b"})

    assert resp.status_code == 200
    assert resp.data.count(b'"token": "\\n"') == 0
    assert b'"token": "ok\\n"' in resp.data


def test_batch_streams_with_system_prompt(client, monkeypatch):
    captured = {}

    def fake_chat_stream(history, model):
        captured["history"] = history
        captured["model"] = model
        yield "ok"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post(
        "/api/batch",
        json={"message": "Frage", "model": "qwen3:14b", "system_prompt": "System"},
    )

    assert resp.status_code == 200
    assert captured == {
        "history": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Frage"},
        ],
        "model": "qwen3:14b",
    }


def test_batch_does_not_create_session(client, monkeypatch):
    def fake_chat_stream(history, model):
        yield "ok"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/batch", json={"message": "Frage", "model": "qwen3:14b"})

    assert resp.status_code == 200
    assert client.get("/api/sessions").get_json() == []


def test_delete_session(client):
    resp = client.post("/api/sessions?user=test", json={"title": "To Delete"})
    sid = resp.get_json()["id"]

    resp = client.delete(f"/api/sessions/{sid}?user=test")
    assert resp.status_code == 200

    resp = client.get("/api/sessions?user=test")
    assert len(resp.get_json()) == 0


def test_search_endpoint(client):
    resp = client.post("/api/search", json={"query": ""})
    assert resp.status_code == 400

    resp = client.post("/api/search", json={"query": "test"})
    assert resp.status_code == 200


def test_get_chat_messages(client):
    resp = client.post("/api/sessions?user=test", json={"title": "Msg Test"})
    sid = resp.get_json()["id"]

    resp = client.get(f"/api/chat/{sid}/messages?user=test")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_update_session_title(client):
    resp = client.post("/api/sessions?user=test", json={"title": "Old"})
    sid = resp.get_json()["id"]

    resp = client.put(f"/api/sessions/{sid}?user=test", json={"title": "New Title"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "New Title"


def test_update_session_rejects_empty_title(client):
    resp = client.post("/api/sessions?user=test", json={"title": "Test"})
    sid = resp.get_json()["id"]

    resp = client.put(f"/api/sessions/{sid}?user=test", json={"title": "  "})
    assert resp.status_code == 400


def test_export_md(client):
    resp = client.post("/api/sessions?user=test", json={"title": "Export Test"})
    sid = resp.get_json()["id"]
    resp = client.get(f"/api/chat/{sid}/export?fmt=md&user=test")
    assert resp.status_code == 200
    assert "text/markdown" in resp.content_type


def test_export_ipynb(client):
    resp = client.post("/api/sessions?user=test", json={"title": "ipynb Test"})
    sid = resp.get_json()["id"]
    resp = client.get(f"/api/chat/{sid}/export?fmt=ipynb&user=test")
    assert resp.status_code == 200
    assert "ipynb" in resp.content_type


def test_export_nonexistent_session(client):
    resp = client.get("/api/chat/99999/export?fmt=md")
    assert resp.status_code == 404


def test_index_has_no_duplicate_ids(client):
    resp = client.get("/")
    html = resp.data.decode()
    assert 'id="user-btn"' in html
    assert 'id="user-menu"' in html
    assert 'id="user-input"' in html
    assert 'id="sidebar-toggle"' in html
    assert 'id="sidebar-overlay"' in html
    assert html.count('id="user-input"') == 1


def test_users_endpoint(client):
    client.post("/api/sessions?user=alice", json={"title": "A1"})
    client.post("/api/sessions?user=alice", json={"title": "A2"})
    client.post("/api/sessions?user=bob", json={"title": "B1"})

    resp = client.get("/api/users")
    assert resp.status_code == 200
    users = resp.get_json()
    by_name = {u["name"]: u["chats"] for u in users}
    assert by_name["alice"] == 2
    assert by_name["bob"] == 1
    assert by_name["default"] == 0


def test_create_user_endpoint(client):
    resp = client.post("/api/users", json={"name": "alice"})
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "alice"

    resp = client.get("/api/users")
    by_name = {u["name"]: u["chats"] for u in resp.get_json()}
    assert by_name["alice"] == 0


def test_rename_user_endpoint_updates_sessions(client):
    client.post("/api/sessions?user=alice", json={"title": "A1"})

    resp = client.put("/api/users/alice", json={"name": "carla"})

    assert resp.status_code == 200
    assert resp.get_json()["name"] == "carla"
    assert client.get("/api/sessions?user=alice").get_json() == []
    sessions = client.get("/api/sessions?user=carla").get_json()
    assert len(sessions) == 1
    assert sessions[0]["title"] == "A1"


def test_rename_user_endpoint_rejects_default_and_conflicts(client):
    client.post("/api/users", json={"name": "alice"})
    client.post("/api/users", json={"name": "bob"})

    assert client.put("/api/users/default", json={"name": "other"}).status_code == 400
    assert client.put("/api/users/alice", json={"name": "bob"}).status_code == 409


def test_delete_user_endpoint_removes_sessions(client):
    client.post("/api/sessions?user=alice", json={"title": "A1"})
    client.post("/api/sessions?user=alice", json={"title": "A2"})

    resp = client.delete("/api/users/alice")

    assert resp.status_code == 200
    assert resp.get_json()["deleted_chats"] == 2
    assert client.get("/api/sessions?user=alice").get_json() == []
    by_name = {u["name"]: u["chats"] for u in client.get("/api/users").get_json()}
    assert "alice" not in by_name


def test_delete_user_endpoint_rejects_default(client):
    resp = client.delete("/api/users/default")

    assert resp.status_code == 400


def test_invalid_user_rejected(client):
    resp = client.post("/api/users", json={"name": "../bad"})
    assert resp.status_code == 400

    resp = client.get("/api/sessions?user=../bad")
    assert resp.status_code == 400


def test_session_routes_check_user_ownership(client):
    resp = client.post("/api/sessions?user=alice", json={"title": "Private"})
    sid = resp.get_json()["id"]

    assert client.get(f"/api/chat/{sid}/messages?user=bob").status_code == 404
    assert client.put(f"/api/sessions/{sid}?user=bob", json={"title": "Wrong"}).status_code == 404
    assert client.delete(f"/api/sessions/{sid}?user=bob").status_code == 404
    assert client.get(f"/api/chat/{sid}/export?fmt=md&user=bob").status_code == 404

    resp = client.get("/api/sessions?user=alice")
    assert resp.get_json()[0]["title"] == "Private"


def test_chat_post_checks_user_ownership(client):
    resp = client.post("/api/sessions?user=alice", json={"title": "Private", "model": "m"})
    sid = resp.get_json()["id"]

    resp = client.post(
        "/api/chat?user=bob",
        json={"session_id": sid, "message": "hi", "model": "m"},
    )

    assert resp.status_code == 404


def test_chat_search_appends_grounded_current_results(client, monkeypatch):
    from datetime import datetime
    from llmflask.services import search_client

    captured = {}

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 21)

    def fake_chat_stream(history, model):
        captured["history"] = history
        captured["model"] = model
        yield "ok"

    monkeypatch.setattr(search_client, "datetime", FixedDatetime)
    monkeypatch.setattr(
        "llmflask.routes.chat.search",
        lambda query: [{
            "title": "Weather",
            "content": "25 C",
            "url": "https://example.test",
        }],
    )
    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    session = client.post(
        "/api/sessions",
        json={"title": "Search", "model": "ollama/qwen3:4b"},
    ).get_json()
    response = client.post(
        "/api/chat",
        json={
            "session_id": session["id"],
            "message": "Weather today?",
            "model": "ollama/qwen3:4b",
            "search": True,
        },
    )

    assert response.status_code == 200
    assert captured["model"] == "ollama/qwen3:4b"
    assert len(captured["history"]) == 1
    message = captured["history"][0]
    assert message["role"] == "user"
    assert message["content"].startswith(
        "Weather today?\n\nCurrent date: 2026-08-21.\n"
        "The following web search results are current.\n"
    )
    assert "prefer these search results over training knowledge" in message["content"]
    assert "https://example.test" in message["content"]


def test_chat_limits_history_for_ollama(client, monkeypatch):
    from llmflask import database

    captured = {}

    def fake_chat_stream(history, model):
        captured["history"] = history
        captured["model"] = model
        yield "ok"

    monkeypatch.setattr("llmflask.routes.chat.MAX_CONTEXT_MESSAGES", 3)
    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/sessions?user=alice", json={"title": "Long", "model": "llama3"})
    sid = resp.get_json()["id"]
    db_path = client.application.config["DB_PATH"]
    for idx in range(5):
        database.add_message(db_path, sid, "user", f"old-{idx}")

    resp = client.post(
        "/api/chat?user=alice",
        json={"session_id": sid, "message": "new", "model": "llama3"},
    )

    assert resp.status_code == 200
    assert b'"done": true' in resp.data
    assert captured["model"] == "llama3"
    assert [msg["content"] for msg in captured["history"]] == ["old-3", "old-4", "new"]


def test_chat_streams_and_stores_final_newline(client, monkeypatch):
    from llmflask import database

    def fake_chat_stream(history, model):
        yield "ok"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/sessions?user=alice", json={"title": "Chat", "model": "llama3"})
    sid = resp.get_json()["id"]

    resp = client.post(
        "/api/chat?user=alice",
        json={"session_id": sid, "message": "new", "model": "llama3"},
    )

    assert resp.status_code == 200
    assert b'"token": "\\n"' in resp.data
    messages = database.get_messages(client.application.config["DB_PATH"], sid)
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "ok\n"


def test_chat_does_not_duplicate_final_newline(client, monkeypatch):
    from llmflask import database

    def fake_chat_stream(history, model):
        yield "ok\n"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/sessions?user=alice", json={"title": "Chat", "model": "llama3"})
    sid = resp.get_json()["id"]

    resp = client.post(
        "/api/chat?user=alice",
        json={"session_id": sid, "message": "new", "model": "llama3"},
    )

    assert resp.status_code == 200
    assert resp.data.count(b'"token": "\\n"') == 0
    messages = database.get_messages(client.application.config["DB_PATH"], sid)
    assert messages[-1]["content"] == "ok\n"


def test_chat_prepends_transient_system_prompt(client, monkeypatch):
    captured = {}

    def fake_chat_stream(history, model):
        captured["history"] = history
        captured["model"] = model
        yield "ok"

    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/sessions?user=alice", json={"title": "Chat", "model": "llama3"})
    sid = resp.get_json()["id"]

    resp = client.post(
        "/api/chat?user=alice",
        json={
            "session_id": sid,
            "message": "new",
            "model": "llama3",
            "system_prompt": "Systemprompt",
        },
    )

    assert resp.status_code == 200
    assert captured["model"] == "llama3"
    assert captured["history"] == [
        {"role": "system", "content": "Systemprompt"},
        {
            "role": "system",
            "content": "The user chatting with you is named alice. You may address them by name if appropriate.",
        },
        {"role": "user", "content": "new"},
    ]


@pytest.mark.parametrize("model", ["openai/gpt-test", "deepseek/deepseek-test"])
def test_chat_keeps_full_history_for_remote_models(client, monkeypatch, model):
    from llmflask import database

    captured = {}

    def fake_chat_stream(history, selected_model):
        captured["history"] = history
        captured["model"] = selected_model
        yield "ok"

    monkeypatch.setattr("llmflask.routes.chat.MAX_CONTEXT_MESSAGES", 3)
    monkeypatch.setattr("llmflask.routes.chat.chat_stream", fake_chat_stream)

    resp = client.post("/api/sessions?user=alice", json={"title": "Long", "model": model})
    sid = resp.get_json()["id"]
    db_path = client.application.config["DB_PATH"]
    for idx in range(5):
        database.add_message(db_path, sid, "user", f"old-{idx}")

    resp = client.post(
        "/api/chat?user=alice",
        json={"session_id": sid, "message": "new", "model": model},
    )

    assert resp.status_code == 200
    assert b'"done": true' in resp.data
    assert captured["model"] == model
    assert [msg["content"] for msg in captured["history"]] == [
        "The user chatting with you is named alice. You may address them by name if appropriate.",
        "old-0",
        "old-1",
        "old-2",
        "old-3",
        "old-4",
        "new",
    ]


@pytest.mark.parametrize("ollama_status", ["available", "unreachable", "empty", "http_error", "invalid_json"])
def test_models_discovers_ollama_and_remote_together(client, monkeypatch, caplog, ollama_status):
    import httpx
    from llmflask.services import model_providers

    endpoint = "http://ollama.test:11434"
    monkeypatch.setattr(model_providers, "OLLAMA_URL", endpoint)
    monkeypatch.setattr(model_providers, "REMOTE_PROVIDERS", model_providers._FALLBACK_PROVIDERS)
    monkeypatch.setattr(model_providers, "load_api_keys", lambda: {
        "OPENAI_API_KEY": "test-openai", "DEEPSEEK_API_KEY": "test-deepseek", "ZEN_API_KEY": "test-zen",
    })
    calls = []
    tags = ["gemma4:12b", "qwen3:14b", "llama3.1:8b", "example:cloud"]

    def mock_get(url, **kwargs):
        calls.append(url)
        request = httpx.Request("GET", url)
        if url == f"{endpoint}/api/tags":
            assert kwargs["timeout"] == 10
            if ollama_status == "unreachable":
                raise httpx.ConnectError("unavailable", request=request)
            if ollama_status == "http_error":
                return httpx.Response(503, request=request)
            if ollama_status == "invalid_json":
                return httpx.Response(200, text="invalid", request=request)
            names = tags + [tags[0]] if ollama_status == "available" else []
            return httpx.Response(200, json={"models": [
                {"name": name, "size": 123} for name in names
            ]}, request=request)
        remote_ids = {
            "https://api.openai.com/v1/models": "shared-model",
            "https://api.deepseek.com/models": "shared-model",
            "https://opencode.ai/zen/v1/models": "big-pickle",
        }
        return httpx.Response(200, json={"data": [{"id": remote_ids[url]}]}, request=request)

    monkeypatch.setattr(httpx, "get", mock_get)
    # Repeated discovery must neither cache a failure nor accumulate entries.
    for _ in range(2):
        response = client.get("/api/models")
        assert response.status_code == 200
        models = response.get_json()
        expected_local = [f"ollama/{tag}" for tag in tags] if ollama_status == "available" else []
        assert [model["name"] for model in models] == expected_local + [
            "openai/shared-model", "deepseek/shared-model", "zen/big-pickle",
        ]
        if expected_local:
            assert [model["label"] for model in models[:4]] == [f"Ollama: {tag}" for tag in tags]
            assert all(model["provider"] == "ollama" and model["size"] == 123 for model in models[:4])
    assert calls.count(f"{endpoint}/api/tags") == 2
    if ollama_status == "available":
        assert not caplog.records
    else:
        assert f"{endpoint}/api/tags" in caplog.text
        assert "remote providers remain available" in caplog.text
        assert ("No Ollama models found" if ollama_status == "empty" else "Ollama model discovery failed") in caplog.text

    ollama_status = "available"
    assert client.get("/api/models").get_json()[0]["name"] == "ollama/gemma4:12b"


@pytest.mark.parametrize("keys", [{}, {"ZEN_API_KEY": "test-zen"}, {
    "OPENAI_API_KEY": "test-openai", "DEEPSEEK_API_KEY": "test-deepseek", "ZEN_API_KEY": "test-zen",
}])
def test_web_tui_cli_share_available_models(client, monkeypatch, capsys, keys):
    import sys
    import httpx
    from llmflask import cli, __main__ as main
    from llmflask.services import model_providers as providers

    monkeypatch.setattr(providers, "REMOTE_PROVIDERS", providers._FALLBACK_PROVIDERS)
    monkeypatch.setattr(providers, "load_api_keys", lambda: keys)
    monkeypatch.setattr("llmflask.model_discovery.load_api_keys", lambda: keys)
    monkeypatch.setattr(cli, "load_api_keys", lambda: keys)
    local = ["ollama/llama3.2:3b", "ollama/qwen3:8b", "ollama/example:cloud"]
    expected = local + (["zen/example-free"] if keys.get("ZEN_API_KEY") else []) + [
        f"{p.name}/example-free" for p in providers.REMOTE_PROVIDERS.values()
        if p.name != "zen" and keys.get(p.api_key_name)
    ]

    def mock_get(url, **kwargs):
        if url.endswith("/api/tags"):
            data = {"models": [{"name": ref.split("/", 1)[1]} for ref in local]}
        else:
            provider = next(p for p in providers.REMOTE_PROVIDERS.values() if url == f"{p.base_url}/models")
            assert keys.get(provider.api_key_name), "Unconfigured providers must not be queried"
            assert kwargs["headers"]["Authorization"] == f"Bearer {keys[provider.api_key_name]}"
            data = {"data": [{"id": "example-free"}, {"id": "example-free"}]}
        return httpx.Response(200, json=data, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", mock_get)
    models = client.get("/api/models").get_json()
    assert [m["name"] for m in models] == expected
    monkeypatch.setattr(cli, "_api_get", lambda url, *args: client.get("/api/models").get_json())
    state = cli.TuiState("127.0.0.1", 5000, "alice", "server")
    cli._load_models(state)
    assert state.models == models
    assert state.current_model == local[0]

    for provider, refs, code in [(None, expected, 0), ("ollama", local, 0),
                                 ("zen", ["zen/example-free"] if keys.get("ZEN_API_KEY") else [],
                                  0 if keys.get("ZEN_API_KEY") else 1)]:
        argv = ["llmflask", "--models"] + (["--provider", provider] if provider else [])
        monkeypatch.setattr(sys, "argv", argv)
        assert main.main() == code
        output = capsys.readouterr()
        if code:
            assert "ZEN_API_KEY is not configured" in output.err
            assert not output.out
        else:
            assert output.out.splitlines()[0] == "MODELREF\tPROVIDER\tLABEL\tSIZE\tVRAM"
            assert [line.split("\t")[0] for line in output.out.splitlines()[1:]] == refs

    direct = cli.TuiState("127.0.0.1", 5000, "alice", "zen")
    cli._load_models(direct)
    assert [m["name"] for m in direct.models] == (["zen/example-free"] if keys.get("ZEN_API_KEY") else [])
    if not keys.get("ZEN_API_KEY"):
        assert "API key is not set" in direct.error
