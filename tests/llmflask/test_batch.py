# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from io import StringIO

import pytest

from llmflask.batch import (
    build_messages,
    load_prompt,
    resolve_prompt_file,
    run_batch_command,
    run_server_batch_command,
)


def test_build_messages_without_prompt():
    assert build_messages("Hallo") == [{"role": "user", "content": "Hallo"}]


def test_build_messages_with_prompt():
    assert build_messages("Hallo", "Antworte knapp.") == [
        {"role": "system", "content": "Antworte knapp."},
        {"role": "user", "content": "Hallo"},
    ]


def test_resolve_prompt_filename_prefers_prompts_dir(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    prompt_file = prompts_dir / "benchmark.md"
    prompt_file.write_text("System", encoding="utf-8")
    (tmp_path / "benchmark.md").write_text("Fallback", encoding="utf-8")

    assert resolve_prompt_file("benchmark.md", tmp_path) == prompt_file


def test_resolve_prompt_explicit_relative_path(tmp_path):
    explicit_dir = tmp_path / "custom"
    explicit_dir.mkdir()
    prompt_file = explicit_dir / "prompt.md"
    prompt_file.write_text("System", encoding="utf-8")

    assert resolve_prompt_file("custom/prompt.md", tmp_path) == prompt_file


def test_resolve_prompt_absolute_path(tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("System", encoding="utf-8")

    assert resolve_prompt_file(str(prompt_file), tmp_path) == prompt_file


def test_load_prompt_rejects_missing_file(tmp_path):
    with pytest.raises(ValueError, match="Prompt file not found"):
        load_prompt("fehlt.md", tmp_path)


def test_load_prompt_rejects_empty_file(tmp_path):
    prompt_file = tmp_path / "empty.md"
    prompt_file.write_text(" \n", encoding="utf-8")

    with pytest.raises(ValueError, match="Prompt file is empty"):
        load_prompt(str(prompt_file), tmp_path)


def test_run_batch_command_streams_tokens(monkeypatch):
    calls = []

    def fake_chat_stream(messages, model):
        calls.append((messages, model))
        yield "Hel"
        yield "lo"

    monkeypatch.setattr("llmflask.batch.chat_stream", fake_chat_stream)
    stdout = StringIO()

    assert run_batch_command("Frage", "llama3.1:8b", stdout=stdout) == 0
    assert stdout.getvalue() == "Hello\n"
    assert calls == [([{"role": "user", "content": "Frage"}], "llama3.1:8b")]


def test_run_batch_command_does_not_duplicate_final_newline(monkeypatch):
    def fake_chat_stream(messages, model):
        yield "Hello\n"

    monkeypatch.setattr("llmflask.batch.chat_stream", fake_chat_stream)
    stdout = StringIO()

    assert run_batch_command("Frage", "llama3.1:8b", stdout=stdout) == 0
    assert stdout.getvalue() == "Hello\n"


def test_run_batch_command_adds_prompt_message(monkeypatch, tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Systemprompt", encoding="utf-8")
    calls = []

    def fake_chat_stream(messages, model):
        calls.append((messages, model))
        yield "ok"

    monkeypatch.setattr("llmflask.batch.chat_stream", fake_chat_stream)

    assert run_batch_command("Frage", "llama3.1:8b", str(prompt_file), stdout=StringIO()) == 0
    assert calls == [
        (
            [
                {"role": "system", "content": "Systemprompt"},
                {"role": "user", "content": "Frage"},
            ],
            "llama3.1:8b",
        )
    ]


def test_run_batch_command_propagates_provider_errors(monkeypatch):
    def fake_chat_stream(messages, model):
        raise RuntimeError("Provider kaputt")
        yield ""

    monkeypatch.setattr("llmflask.batch.chat_stream", fake_chat_stream)

    with pytest.raises(RuntimeError, match="Provider kaputt"):
        run_batch_command("Frage", "llama3.1:8b", stdout=StringIO())


def test_run_server_batch_command_streams_sse_tokens(monkeypatch):
    captured = {}

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield 'data: {"token": "Hel", "done": false}'
            yield 'data: {"token": "lo", "done": false}'
            yield 'data: {"token": "", "done": true}'

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def stream(self, method, url, json=None):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = json
            return MockResponse()

    monkeypatch.setattr("llmflask.batch.httpx.Client", MockClient)
    stdout = StringIO()

    assert run_server_batch_command("Frage", "qwen3:14b", "http://127.0.0.1:60010", stdout=stdout) == 0
    assert stdout.getvalue() == "Hello\n"
    assert captured == {
        "method": "POST",
        "url": "http://127.0.0.1:60010/api/batch",
        "json": {"message": "Frage", "model": "qwen3:14b"},
    }


def test_run_server_batch_command_does_not_duplicate_final_newline(monkeypatch):
    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield 'data: {"token": "Hello\\n", "done": false}'
            yield 'data: {"token": "", "done": true}'

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def stream(self, method, url, json=None):
            return MockResponse()

    monkeypatch.setattr("llmflask.batch.httpx.Client", MockClient)
    stdout = StringIO()

    assert run_server_batch_command("Frage", "qwen3:14b", "http://server", stdout=stdout) == 0
    assert stdout.getvalue() == "Hello\n"


def test_run_server_batch_command_sends_prompt(monkeypatch, tmp_path):
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("System", encoding="utf-8")
    captured = {}

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield 'data: {"token": "ok", "done": false}'
            yield 'data: {"token": "", "done": true}'

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def stream(self, method, url, json=None):
            captured["json"] = json
            return MockResponse()

    monkeypatch.setattr("llmflask.batch.httpx.Client", MockClient)

    run_server_batch_command("Frage", "qwen3:14b", "http://server", str(prompt_file), stdout=StringIO())

    assert captured["json"] == {"message": "Frage", "model": "qwen3:14b", "system_prompt": "System"}


def test_run_server_batch_command_raises_sse_error(monkeypatch):
    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield 'data: {"error": "Provider kaputt", "done": true}'

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def stream(self, method, url, json=None):
            return MockResponse()

    monkeypatch.setattr("llmflask.batch.httpx.Client", MockClient)

    with pytest.raises(RuntimeError, match="Provider kaputt"):
        run_server_batch_command("Frage", "qwen3:14b", "http://server", stdout=StringIO())


def test_direct_batch_rejects_session_owned_by_another_user(monkeypatch, tmp_path):
    from llmflask import config
    from llmflask.batch import run_batch_command
    from llmflask.database import create_session, init_db

    database = str(tmp_path / "chat.db")
    init_db(database)
    session_id = create_session(database, user="alice")
    monkeypatch.setattr(config, "DATABASE", database)
    called = False

    def fake_chat_stream(messages, model):
        nonlocal called
        called = True
        yield "answer"

    monkeypatch.setattr("llmflask.batch.chat_stream", fake_chat_stream)

    with pytest.raises(ValueError, match="not found for user 'bob'"):
        run_batch_command(
            "question",
            "ollama/qwen3:8b",
            session_id=session_id,
            user="bob",
            stdout=StringIO(),
        )
    assert called is False
