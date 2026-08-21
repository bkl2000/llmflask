# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from io import StringIO

import pytest


def test_cli_help():
    import sys
    from llmflask.__main__ import main

    sys.argv = ["llmflask", "--help"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_cmd_requires_model(monkeypatch, capsys):
    import sys
    from llmflask.__main__ import main

    monkeypatch.setattr(sys, "argv", ["llmflask", "--cmd", "--text", "Hallo"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert "--cmd requires --model" in capsys.readouterr().err


def test_cmd_argument_runs_batch_runner(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref, stdout))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--cmd", "--text", "Frage", "--model", "llama3.1:8b"])

    assert cli_main.main() == 0
    assert calls == [("Frage", "llama3.1:8b", None, sys.stdout)]


def test_cmd_with_explicit_port_runs_server_batch_runner(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    local_calls = []
    server_calls = []

    def fake_run_batch_command(*args, **kwargs):
        local_calls.append((args, kwargs))
        return 0

    def fake_run_server_batch_command(question, model, base_url, prompt_ref=None, session_id=None, user=None, stdout=None, search=False):
        server_calls.append((question, model, base_url, prompt_ref, stdout))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(cli_main, "run_server_batch_command", fake_run_server_batch_command)
    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--text", "Frage", "--model", "qwen3:14b", "--port", "60010"],
    )

    assert cli_main.main() == 0
    assert local_calls == []
    assert server_calls == [("Frage", "qwen3:14b", "http://127.0.0.1:60010", None, sys.stdout)]


def test_cmd_with_explicit_host_runs_server_batch_runner(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_server_batch_command(question, model, base_url, prompt_ref=None, session_id=None, user=None, stdout=None, search=False):
        calls.append((question, model, base_url, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_server_batch_command", fake_run_server_batch_command)
    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--text", "Frage", "--model", "qwen3:14b", "--host", "server.local"],
    )

    assert cli_main.main() == 0
    assert calls == [("Frage", "qwen3:14b", "http://server.local:5000", None)]


def test_cmd_without_argument_reads_stdin(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--cmd", "--model", "llama3.1:8b"])
    monkeypatch.setattr(sys, "stdin", StringIO("Frage aus stdin\nzweite Zeile"))

    assert cli_main.main() == 0
    assert calls == [("Frage aus stdin\nzweite Zeile", "llama3.1:8b", None)]


def test_cmd_positional_text_after_flags(monkeypatch):
    """llmflask --cmd --model qwen3:14b hello world"""
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--model", "qwen3:14b", "hello", "world"],
    )

    assert cli_main.main() == 0
    assert calls == [("hello world", "qwen3:14b", None)]


def test_cmd_positional_text_with_host(monkeypatch):
    """llmflask --host 192.0.2.164 --model ollama/qwen3:14b --cmd Hello"""
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_server_batch_command(question, model, base_url, prompt_ref=None, session_id=None, user=None, stdout=None, search=False):
        calls.append((question, model, base_url, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_server_batch_command", fake_run_server_batch_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--host", "192.0.2.164", "--model", "ollama/qwen3:14b", "--cmd", "Hello"],
    )

    assert cli_main.main() == 0
    assert calls == [("Hello", "ollama/qwen3:14b", "http://192.0.2.164:5000", None)]


def test_cmd_positional_text_with_provider(monkeypatch):
    """llmflask --cmd --provider deepseek --model deepseek-chat hello"""
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--provider", "deepseek", "--model", "deepseek-chat", "hello"],
    )

    assert cli_main.main() == 0
    assert calls == [("hello", "deepseek/deepseek-chat", None)]


def test_cmd_positional_text_multiple_words(monkeypatch):
    """llmflask --cmd --model m what is the meaning of life"""
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--model", "qwen3:14b", "what", "is", "the", "meaning", "of", "life"],
    )

    assert cli_main.main() == 0
    assert calls == [("what is the meaning of life", "qwen3:14b", None)]


def test_cmd_passes_prompt_to_batch_runner(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--text", "Frage", "--model", "llama3.1:8b", "--prompt", "benchmark.md"],
    )

    assert cli_main.main() == 0
    assert calls == [("Frage", "llama3.1:8b", "benchmark.md")]


def test_cmd_explicit_text_wins_over_positional(monkeypatch):
    """llmflask --cmd --text hello --model m leftover -- --text takes priority"""
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--text", "explicit", "--model", "qwen3:14b", "trailing"],
    )

    assert cli_main.main() == 0
    assert calls == [("explicit", "qwen3:14b", None)]


def test_cmd_keyboard_interrupt_during_stdin(monkeypatch):
    import sys
    from io import StringIO
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--model", "qwen3:14b"],
    )

    interrupt_calls = []

    class FakeStdin:
        def read(self):
            interrupt_calls.append("read")
            raise KeyboardInterrupt

    monkeypatch.setattr(sys, "stdin", FakeStdin())

    result = cli_main.main()
    assert result == 130
    assert interrupt_calls == ["read"]


def test_cmd_keyboard_interrupt_during_usepool_stdin(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--usepool", "--model", "qwen3:14b"],
    )

    interrupt_calls = []

    class FakeStdin:
        def read(self):
            interrupt_calls.append("read")
            raise KeyboardInterrupt

    monkeypatch.setattr(sys, "stdin", FakeStdin())

    result = cli_main.main()
    assert result == 130
    assert interrupt_calls == ["read"]


def test_cmd_positional_text_with_session_and_prompt(monkeypatch):
    """llmflask --cmd --model m --session 1 --prompt p.md hello"""
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    monkeypatch.setattr(
        "llmflask.database.get_session_for_user",
        lambda db_path, session_id, user: True,
    )
    calls = []

    def fake_run_batch_command(question, model, prompt_ref=None, session_id=None, user=None, stdout=None):
        calls.append((question, model, prompt_ref, session_id))
        return 0

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--cmd", "--model", "qwen3:14b", "--session", "1", "--prompt", "p.md", "hello"],
    )

    assert cli_main.main() == 0
    assert calls == [("hello", "qwen3:14b", "p.md", 1)]


def test_cmd_positional_text_no_interference_with_subcommands(monkeypatch):
    """pool list should still work as subcommand, not be consumed as --cmd text"""
    import sys
    from llmflask.__main__ import _build_parser, _extract_positional_text

    parser = _build_parser()

    argv = ["llmflask", "pool", "list"]
    processed, text = _extract_positional_text(argv)
    # pool is a subcommand, so it should NOT be extracted as text
    assert text is None
    assert "pool" in processed
    assert "list" in processed

    args = parser.parse_args(processed[1:])
    assert args.command == "pool"
    assert getattr(args, "pool_action", None) == "list"


def test_cmd_positional_text_does_not_affect_pool_run(monkeypatch):
    """pool run mypool --model m should still work"""
    import sys
    from llmflask.__main__ import _build_parser, _extract_positional_text

    parser = _build_parser()

    argv = ["llmflask", "pool", "run", "mypool", "--model", "qwen3:14b"]
    processed, text = _extract_positional_text(argv)
    assert text is None
    assert "pool" in processed
    assert "run" in processed
    assert "mypool" in processed

    args = parser.parse_args(processed[1:])
    assert args.command == "pool"
    assert getattr(args, "pool_action", None) == "run"


def test_extract_positional_text_no_cmd_flag():
    """Without --cmd, argv is returned unchanged."""
    from llmflask.__main__ import _extract_positional_text

    argv = ["llmflask", "--models"]
    result, text = _extract_positional_text(argv)
    assert result == argv
    assert text is None


def test_extract_positional_text_single_word():
    from llmflask.__main__ import _extract_positional_text

    argv = ["llmflask", "--cmd", "--model", "qwen3:14b", "hello"]
    result, text = _extract_positional_text(argv)
    assert text == "hello"
    assert result == ["llmflask", "--cmd", "--model", "qwen3:14b", "--text", "hello"]


def test_extract_positional_text_with_explicit_text():
    """When --text is already given, trailing positionals are NOT extracted."""
    from llmflask.__main__ import _extract_positional_text

    argv = ["llmflask", "--cmd", "--text", "explicit", "--model", "qwen3:14b", "trailing"]
    result, text = _extract_positional_text(argv)
    assert text is None
    assert "--text" in result
    assert "trailing" not in result  # silently dropped when --text is given


def test_extract_positional_text_subcommand_stops_extraction():
    """'pool' as first positional (no preceding text) is a subcommand."""
    from llmflask.__main__ import _extract_positional_text

    argv = ["llmflask", "pool", "list"]
    result, text = _extract_positional_text(argv)
    assert text is None  # pool is the subcommand, no text extracted
    assert result == argv

    # "pool" in the middle of text stays as text
    argv2 = ["llmflask", "--cmd", "--model", "m", "hello", "pool", "list"]
    result2, text2 = _extract_positional_text(argv2)
    assert text2 == "hello pool list"


def test_extract_positional_text_value_flags_not_treated_as_text():
    """Flag values should not be extracted as text."""
    from llmflask.__main__ import _extract_positional_text

    argv = ["llmflask", "--cmd", "--host", "192.0.2.164", "--model", "qwen3:14b", "hello"]
    result, text = _extract_positional_text(argv)
    assert text == "hello"
    assert "--host" in result
    assert "192.0.2.164" in result


def test_usepool_positional_text(monkeypatch):
    """llmflask --usepool --model qwen3:14b write a script"""
    import sys
    from llmflask import __main__ as cli_main

    pool_calls = []

    def fake_run_pool_cli(source, request_text, model_ref, host, port, pool_name=None, reuse=False, result_dir=None):
        pool_calls.append((source, request_text, model_ref, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda host, port, model_ref, use_server: True)
    monkeypatch.setattr(cli_main, "_run_pool_cli", fake_run_pool_cli)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--usepool", "--model", "qwen3:14b", "write", "a", "script"],
    )

    assert cli_main.main() == 0
    assert pool_calls[0][1] == "write a script"


def test_usepool_positional_text_with_host_and_file(monkeypatch):
    """llmflask --usepool --host 0.0.0.0 --model m --file data.csv analyze this"""
    import sys
    from llmflask import __main__ as cli_main

    pool_calls = []

    def fake_run_pool_cli(source, request_text, model_ref, host, port, pool_name=None, reuse=False, result_dir=None):
        pool_calls.append((source, request_text, model_ref, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda host, port, model_ref, use_server: True)
    monkeypatch.setattr(cli_main, "_run_pool_cli", fake_run_pool_cli)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--usepool", "--host", "192.0.2.164", "--model", "qwen3:14b", "--file", "data.csv", "analyze", "this"],
    )

    assert cli_main.main() == 0
    assert pool_calls[0][1] == "analyze this"
    assert pool_calls[0][0] == "data.csv"
    assert pool_calls[0][3] == "192.0.2.164"


def test_usepool_explicit_text_wins(monkeypatch):
    """llmflask --usepool --text explicit --model m trailing"""
    import sys
    from llmflask import __main__ as cli_main

    pool_calls = []

    def fake_run_pool_cli(source, request_text, model_ref, host, port, pool_name=None, reuse=False, result_dir=None):
        pool_calls.append(request_text)
        return 0

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda host, port, model_ref, use_server: True)
    monkeypatch.setattr(cli_main, "_run_pool_cli", fake_run_pool_cli)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--usepool", "--text", "explicit", "--model", "qwen3:14b", "trailing"],
    )

    assert cli_main.main() == 0
    assert pool_calls == ["explicit"]


def test_validate_model_ref_known_passes(monkeypatch):
    from llmflask.__main__ import _validate_model_ref

    def fake_server_models(host, port):
        return [{"name": "ollama/qwen3:14b", "provider": "ollama", "label": "Ollama: qwen3:14b"}]

    monkeypatch.setattr("llmflask.model_discovery._server_models", fake_server_models)
    assert _validate_model_ref("127.0.0.1", 5000, "ollama/qwen3:14b", use_server=True) is True


def test_validate_model_ref_unknown_fails_and_prints(monkeypatch, capsys):
    from llmflask.__main__ import _validate_model_ref

    def fake_server_models(host, port):
        return [{"name": "ollama/qwen3:14b", "provider": "ollama", "label": "Ollama: qwen3:14b"}]

    monkeypatch.setattr("llmflask.model_discovery._server_models", fake_server_models)
    result = _validate_model_ref("127.0.0.1", 5000, "ollama/nonexistent", use_server=True)
    assert result is False
    assert "not found" in capsys.readouterr().err


def test_validate_model_ref_error_returns_true(monkeypatch):
    from llmflask.__main__ import _validate_model_ref

    def fake_server_models(host, port):
        raise ConnectionError

    monkeypatch.setattr("llmflask.model_discovery._server_models", fake_server_models)
    result = _validate_model_ref("127.0.0.1", 5000, "ollama/qwen3:14b", use_server=True)
    assert result is False


def test_extract_positional_text_usepool():
    """--usepool also works with positional text."""
    from llmflask.__main__ import _extract_positional_text

    argv = ["llmflask", "--usepool", "--model", "qwen3:14b", "hello", "world"]
    result, text = _extract_positional_text(argv)
    assert text == "hello world"
    assert result == ["llmflask", "--usepool", "--model", "qwen3:14b", "--text", "hello world"]


def test_prompt_without_cmd_is_error(monkeypatch, capsys):
    import sys
    from llmflask.__main__ import main

    monkeypatch.setattr(sys, "argv", ["llmflask", "--prompt", "benchmark.md"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert "requires --cmd or --tui" in capsys.readouterr().err


def test_tui_prompt_loads_prompt_file(monkeypatch, tmp_path):
    import sys
    import types
    from llmflask.__main__ import main

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("Systemprompt", encoding="utf-8")
    calls = []
    fake_cli = types.ModuleType("llmflask.cli")

    def fake_run_tui(**kwargs):
        calls.append(kwargs)

    fake_cli.run_tui = fake_run_tui
    monkeypatch.setitem(sys.modules, "llmflask.cli", fake_cli)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "llmflask", "--tui", "--provider", "server",
            "--prompt", str(prompt_file), "--user", "alice",
        ],
    )

    main()

    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 5000,
            "user": "alice",
            "trace": False,
            "provider": "server",
            "system_prompt": "Systemprompt",
        }
    ]


def test_tui_prompt_missing_file_is_error(monkeypatch, capsys):
    import sys
    import types
    from llmflask.__main__ import main

    fake_cli = types.ModuleType("llmflask.cli")
    fake_cli.run_tui = lambda **kwargs: None
    monkeypatch.setitem(sys.modules, "llmflask.cli", fake_cli)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--tui", "--provider", "server", "--prompt", "missing.md"],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "Prompt file not found" in captured.err


def test_cmd_validation_error_writes_stderr(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    def fake_run_batch_command(*args, **kwargs):
        raise ValueError("Prompt file not found")

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--cmd", "--text", "Frage", "--model", "llama3.1:8b"])

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "Prompt file not found" in captured.err


def test_cmd_provider_error_returns_nonzero(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    def fake_run_batch_command(*args, **kwargs):
        raise RuntimeError("Provider kaputt")

    monkeypatch.setattr(cli_main, "run_batch_command", fake_run_batch_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--cmd", "--text", "Frage", "--model", "llama3.1:8b"])

    assert cli_main.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Provider kaputt" in captured.err


def test_models_lists_available_model_refs(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        "llmflask.model_discovery.list_models",
        lambda: [
            {"name": "ollama/llama3.1:8b", "provider": "ollama", "label": "Ollama: llama3.1:8b"},
            {"name": "openai/gpt-4.1-mini", "provider": "openai", "label": "OpenAI: gpt-4.1-mini"},
        ],
    )
    monkeypatch.setattr(sys, "argv", ["llmflask", "--models"])

    assert cli_main.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "MODELREF\tPROVIDER\tLABEL\tSIZE\tVRAM" in captured.out
    assert "ollama/llama3.1:8b\tollama\tOllama: llama3.1:8b\t\t" in captured.out
    assert "openai/gpt-4.1-mini\topenai\tOpenAI: gpt-4.1-mini\t\t" in captured.out


def test_models_with_explicit_port_reads_server_models(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_server_models(host, port):
        calls.append((host, port))
        return [{"name": "ollama/qwen3:14b", "provider": "ollama", "label": "Ollama: qwen3:14b"}]

    monkeypatch.setattr("llmflask.model_discovery._server_models", fake_server_models)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--models", "--port", "60010"])

    assert cli_main.main() == 0
    captured = capsys.readouterr()
    assert calls == [("127.0.0.1", 60010)]
    assert captured.err == ""
    assert "ollama/qwen3:14b\tollama\tOllama: qwen3:14b" in captured.out


def test_human_size_formats_bytes():
    from llmflask.model_discovery import _human_size

    assert _human_size(0) == ""
    assert _human_size(2 * 1024**3) == "2.0G"
    assert _human_size(100 * 1024**2) == "100M"


def test_vram_fit_from_parameter_size_details():
    from llmflask.model_discovery import _vram_fit

    assert _vram_fit({"details": {"parameter_size": "3.2B"}}) == "4 GB"
    assert _vram_fit({"details": {"parameter_size": "7.6B"}}) == "8 GB"
    assert _vram_fit({"details": {"parameter_size": "14B"}}) == "12 GB"
    assert _vram_fit({"details": {"parameter_size": "22B"}}) == "16+ GB"
    assert _vram_fit({"details": {"parameter_size": "30.5B"}}) == "24+ GB"
    assert _vram_fit({"details": {"param_size": "1.7B"}}) == "4 GB"
    assert _vram_fit({"id": "llama3.2:3b"}) == "4 GB"
    assert _vram_fit({"id": "openai/gpt-4.1-mini"}) == ""


def test_models_table_includes_size_and_vram_columns(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        "llmflask.model_discovery.list_models",
        lambda: [
            {
                "name": "ollama/llama3.2:3b",
                "provider": "ollama",
                "label": "Ollama: llama3.2:3b",
                "size": 2 * 1024**3,
                "details": {"param_size": "3.2B"},
            },
        ],
    )
    monkeypatch.setattr(sys, "argv", ["llmflask", "--models"])

    assert cli_main.main() == 0
    captured = capsys.readouterr()
    assert "MODELREF\tPROVIDER\tLABEL\tSIZE\tVRAM" in captured.out
    assert "ollama/llama3.2:3b\tollama\tOllama: llama3.2:3b\t2.0G\t4 GB" in captured.out


def test_models_server_error_returns_nonzero(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    def fake_server_models(host, port):
        raise RuntimeError("Connection refused")

    monkeypatch.setattr("llmflask.model_discovery._server_models", fake_server_models)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--models", "--port", "60010"])

    assert cli_main.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Connection refused" in captured.err


def test_models_returns_nonzero_when_no_models(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    monkeypatch.setattr("llmflask.model_discovery.list_models", lambda: [])
    monkeypatch.setattr(sys, "argv", ["llmflask", "--models"])

    assert cli_main.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No models found" in captured.err


def test_cli_default_is_gui():
    from llmflask.__main__ import main as cli_main
    assert cli_main is not None


def test_tui_trace_option_passes_trace_true(monkeypatch):
    import sys
    import types
    from llmflask.__main__ import main

    calls = []
    fake_cli = types.ModuleType("llmflask.cli")

    def fake_run_tui(**kwargs):
        calls.append(kwargs)

    fake_cli.run_tui = fake_run_tui
    monkeypatch.setitem(sys.modules, "llmflask.cli", fake_cli)
    monkeypatch.setattr(
        sys,
        "argv",
        ["llmflask", "--tui", "--provider", "server", "--tui-trace", "--user", "alice"],
    )

    main()

    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 5000,
            "user": "alice",
            "trace": True,
            "provider": "server",
            "system_prompt": None,
        }
    ]


def test_tui_trace_option_defaults_false(monkeypatch):
    import sys
    import types
    from llmflask import __main__ as cli_main

    calls = []
    fake_cli = types.ModuleType("llmflask.cli")

    def fake_run_tui(**kwargs):
        calls.append(kwargs)

    fake_cli.run_tui = fake_run_tui
    monkeypatch.setitem(sys.modules, "llmflask.cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--tui", "--user", "alice"])
    monkeypatch.setattr(cli_main, "_resolve_tui_provider", lambda *args: "server")

    cli_main.main()

    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 5000,
            "user": "alice",
            "trace": False,
            "provider": "server",
            "system_prompt": None,
        }
    ]


def test_tui_without_server_auto_selects_only_configured_provider(monkeypatch):
    import sys
    import types
    from llmflask import __main__ as cli_main

    calls = []
    fake_cli = types.ModuleType("llmflask.cli")
    fake_cli.run_tui = lambda **kwargs: calls.append(kwargs)
    monkeypatch.setitem(sys.modules, "llmflask.cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--tui", "--user", "alice"])
    monkeypatch.setattr("llmflask.model_discovery._local_server_available", lambda host, port: False)
    monkeypatch.setattr(
        "llmflask.model_discovery.load_api_keys",
        lambda: {"DEEPSEEK_API_KEY": "secret"},
    )

    assert cli_main.main() == 0
    assert calls[0]["provider"] == "deepseek"


def test_tui_provider_option_selects_direct_provider(monkeypatch):
    import sys
    import types
    from llmflask.__main__ import main

    calls = []
    fake_cli = types.ModuleType("llmflask.cli")

    def fake_run_tui(**kwargs):
        calls.append(kwargs)

    fake_cli.run_tui = fake_run_tui
    monkeypatch.setitem(sys.modules, "llmflask.cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--tui", "--provider", "deepseek", "--user", "alice"])

    main()

    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 5000,
            "user": "alice",
            "trace": False,
            "provider": "deepseek",
            "system_prompt": None,
        }
    ]


def test_cli_server_production_runs_gunicorn(monkeypatch):
    import sys
    import types
    from llmflask import __main__ as cli_main

    calls = []
    fake_app_module = types.ModuleType("llmflask.app")

    def fake_create_app(**kw):
        return "app"

    def fake_run_gunicorn(app, host, port):
        calls.append((app, host, port))

    fake_app_module.create_app = fake_create_app
    monkeypatch.setitem(sys.modules, "llmflask.app", fake_app_module)
    monkeypatch.setattr(cli_main, "run_gunicorn", fake_run_gunicorn)
    monkeypatch.setattr(cli_main, "_verify_server_requirements", lambda: True)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "production", "--host", "0.0.0.0", "--port", "5050"])

    cli_main.main()

    assert calls == [("app", "0.0.0.0", 5050)]


def test_cli_server_dev_uses_flask_run(monkeypatch):
    import sys
    import types
    from llmflask.__main__ import main

    calls = []
    fake_app_module = types.ModuleType("llmflask.app")

    class FakeApp:
        def run(self, **kwargs):
            calls.append(kwargs)

    fake_app_module.create_app = lambda **kw: FakeApp()
    monkeypatch.setitem(sys.modules, "llmflask.app", fake_app_module)
    monkeypatch.setattr("llmflask.__main__._verify_server_requirements", lambda: True)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--host", "0.0.0.0", "--port", "5050"])

    main()

    assert calls == [{"host": "0.0.0.0", "port": 5050, "debug": False, "threaded": True}]


def test_gunicorn_options_defaults(monkeypatch):
    from llmflask.__main__ import _gunicorn_options

    monkeypatch.delenv("LLMFLASK_GUNICORN_WORKERS", raising=False)
    monkeypatch.delenv("LLMFLASK_GUNICORN_THREADS", raising=False)
    monkeypatch.delenv("LLMFLASK_GUNICORN_TIMEOUT", raising=False)

    assert _gunicorn_options("0.0.0.0", 5000) == {
        "bind": "0.0.0.0:5000",
        "workers": 1,
        "threads": 16,
        "worker_class": "gthread",
        "timeout": 600,
    }


def test_gunicorn_options_env_overrides(monkeypatch):
    from llmflask.__main__ import _gunicorn_options

    monkeypatch.setenv("LLMFLASK_GUNICORN_WORKERS", "2")
    monkeypatch.setenv("LLMFLASK_GUNICORN_THREADS", "8")
    monkeypatch.setenv("LLMFLASK_GUNICORN_TIMEOUT", "300")

    options = _gunicorn_options("127.0.0.1", 5050)

    assert options["bind"] == "127.0.0.1:5050"
    assert options["workers"] == 2
    assert options["threads"] == 8
    assert options["timeout"] == 300


def test_key_constants():
    from llmflask.cli import (
        KEY_CTRL_N, KEY_CTRL_D, KEY_CTRL_E, KEY_CTRL_S, KEY_CTRL_P, KEY_ESC,
    )
    assert KEY_CTRL_N == 14
    assert KEY_CTRL_D == 4
    assert KEY_CTRL_E == 5
    assert KEY_CTRL_S == 19
    assert KEY_CTRL_P == 16
    assert KEY_ESC == 27


def test_tui_state_creation():
    from llmflask.cli import TuiState
    s = TuiState("127.0.0.1", 5000)
    assert s.base == "http://127.0.0.1:5000"
    assert s.focus == 0  # FOCUS_INPUT
    assert not s.search_enabled
    assert s.streaming is False
    assert s.input_text == ""
    assert s.messages == []
    assert s.sessions == []
    assert s.models == []


def test_user_query_encodes_spaces():
    from llmflask.cli import TuiState, _user_query

    s = TuiState("127.0.0.1", 5000, "Alice Smith")

    assert _user_query(s) == "user=Alice+Smith"


def test_draw_resilient_to_small_terminal():
    import curses
    from llmflask.cli import draw, TuiState

    state = TuiState("x", 1, "testuser")

    class MockScreen:
        def getmaxyx(self):
            return (1, 1)
        def erase(self):
            pass
        def refresh(self):
            pass
        def addch(self, *a):
            pass
        def addstr(self, *a):
            pass
        def hline(self, *a):
            pass

    draw(MockScreen(), state)  # should not crash


def test_draw_with_messages(monkeypatch):
    import curses
    from llmflask.cli import draw, TuiState

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)
    monkeypatch.setattr(curses, "KEY_ENTER", 10, raising=False)
    monkeypatch.setattr(curses, "KEY_BACKSPACE", 127, raising=False)
    monkeypatch.setattr(curses, "KEY_UP", 259, raising=False)
    monkeypatch.setattr(curses, "KEY_DOWN", 258, raising=False)
    monkeypatch.setattr(curses, "curs_set", lambda x: None, raising=False)

    state = TuiState("x", 1, "testuser")
    state.messages = [{"role": "user", "content": "hello"}]

    class MockScreen:
        def getmaxyx(self):
            return (24, 120)
        def erase(self):
            pass
        def refresh(self):
            pass
        def addch(self, *a):
            pass
        def addstr(self, *a):
            pass
        def hline(self, *a):
            pass
        def move(self, *a):
            pass

    draw(MockScreen(), state)


def test_run_tui_imports():
    from llmflask.cli import run_tui
    assert callable(run_tui)


def test_wrap_text_short():
    from llmflask.cli import _wrap_text
    result = _wrap_text("hello", 80)
    assert result == ["hello"]


def test_wrap_text_wraps():
    from llmflask.cli import _wrap_text
    result = _wrap_text("a b c d e", 6)
    assert len(result) > 1


def test_wrap_text_empty():
    from llmflask.cli import _wrap_text
    result = _wrap_text("", 10)
    assert result == [""]


def test_wrap_text_narrow():
    from llmflask.cli import _wrap_text
    result = _wrap_text("hello", 0)
    assert result == [""]


def test_wrap_preserves_paragraphs():
    from llmflask.cli import _wrap_text
    text = "First paragraph.\n\nSecond paragraph."
    result = _wrap_text(text, 80)
    assert "" in result  # blank line between paragraphs
    assert result.count("") == 1


def test_wrap_preserves_single_newlines():
    from llmflask.cli import _wrap_text
    text = "Line 1\nLine 2"
    result = _wrap_text(text, 80)
    assert len(result) == 2
    assert result[0] == "Line 1"
    assert result[1] == "Line 2"


def test_draw_multiline(monkeypatch):
    import curses
    from llmflask.cli import draw, TuiState

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)
    monkeypatch.setattr(curses, "KEY_ENTER", 10, raising=False)
    monkeypatch.setattr(curses, "KEY_BACKSPACE", 127, raising=False)
    monkeypatch.setattr(curses, "KEY_UP", 259, raising=False)
    monkeypatch.setattr(curses, "KEY_DOWN", 258, raising=False)
    monkeypatch.setattr(curses, "curs_set", lambda x: None, raising=False)

    state = TuiState("x", 1, "testuser")
    state.messages = [
        {"role": "user", "content": "hello world"},
        {"role": "assistant", "content": "lorem ipsum " * 80},
    ]

    class MockScreen:
        def getmaxyx(self):
            return (30, 120)
        def erase(self):
            pass
        def refresh(self):
            pass
        def addch(self, *a):
            pass
        def addstr(self, *a):
            pass
        def hline(self, *a):
            pass
        def move(self, *a):
            pass

    draw(MockScreen(), state)  # should not crash, should wrap

def test_wch_input_accumulates_multibyte():
    from llmflask.cli import TuiState
    state = TuiState("x", 1, "testuser")

    ch = "ä"
    if isinstance(ch, str) and ch.isprintable():
        state.input_text += ch
    assert state.input_text == "ä"

    ch = "a"
    state.input_text += ch
    assert state.input_text == "äa"


def test_render_md_bold():
    from llmflask.cli import _render_md_line
    import curses
    attr, text = _render_md_line("**hello**")
    assert attr == curses.A_BOLD


def test_render_md_heading():
    from llmflask.cli import _render_md_line
    import curses
    attr, text = _render_md_line("### Title")
    assert attr == curses.A_BOLD


def test_render_md_list():
    from llmflask.cli import _render_md_line
    _, text = _render_md_line("- item")
    assert text.startswith("  ")


def test_render_md_hr():
    from llmflask.cli import _render_md_line
    _, text = _render_md_line("---")
    assert "─" in text


def test_render_md_code():
    from llmflask.cli import _render_md_line
    import curses
    attr, text = _render_md_line("```python\ncode\n```")
    assert attr == curses.A_DIM


def test_render_message_lines_preserves_fenced_code_indent():
    from llmflask.cli import _render_message_lines
    import curses

    content = "```python\ndef values():\n    yield 1\n    yield from other()\n```"

    lines = _render_message_lines(content, 80)

    assert (curses.A_DIM, "    yield 1") in lines
    assert (curses.A_DIM, "    yield from other()") in lines


def test_render_message_lines_preserves_indented_code_indent():
    from llmflask.cli import _render_message_lines
    import curses

    lines = _render_message_lines("Example:\n    print('hello')", 80)

    assert (curses.A_DIM, "    print('hello')") in lines


def test_scroll_state_added():
    from llmflask.cli import TuiState
    s = TuiState("x", 1, "testuser")
    assert s.scroll_offset == 0
    assert s.chat_max_scroll == 0
    assert s.follow_tail is True


def test_page_keys_scroll_in_input_focus(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_PPAGE", 339, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_NPAGE", 338, raising=False)

    state = TuiState("x", 1, "testuser")
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 339) is None
    assert state.scroll_offset == 20
    assert state.follow_tail is False

    assert cli._handle_key(state, 338) is None
    assert state.scroll_offset == 30
    assert state.follow_tail is True

    assert cli._handle_key(state, 338) is None
    assert state.scroll_offset == 30
    assert state.follow_tail is True


def test_page_up_still_scrolls_after_page_down_reaches_bottom(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_PPAGE", 339, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_NPAGE", 338, raising=False)

    state = TuiState("x", 1, "testuser")
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 339) is None
    assert state.scroll_offset == 20

    assert cli._handle_key(state, 338) is None
    assert state.scroll_offset == 30

    assert cli._handle_key(state, 339) is None
    assert state.scroll_offset == 20


def test_page_key_escape_sequences_scroll_without_input_pollution(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_PPAGE", 339, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_NPAGE", 338, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, "\x1b[5~") is None
    assert state.scroll_offset == 20
    assert state.input_text == "hello"

    assert cli._handle_key(state, "\x1b[6~") is None
    assert state.scroll_offset == 30
    assert state.input_text == "hello"


def test_page_up_unicode_fallback_scrolls_without_input_pollution(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_PPAGE", 339, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_NPAGE", 338, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, "Ć") is None
    assert state.scroll_offset == 20
    assert state.input_text == "hello"

    assert cli._handle_key(state, "Ć") is None
    assert state.scroll_offset == 10
    assert state.input_text == "hello"

    assert cli._handle_key(state, 338) is None
    assert state.scroll_offset == 20

    assert cli._handle_key(state, 338) is None
    assert state.scroll_offset == 30


def test_home_key_jumps_to_top_without_input_pollution(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_HOME", 262, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 262) is None
    assert state.scroll_offset == 0
    assert state.follow_tail is False
    assert state.input_text == "hello"
    assert state.error == ""


def test_end_key_jumps_to_bottom_without_input_pollution(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_END", 360, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"
    state.scroll_offset = 0
    state.chat_max_scroll = 30
    state.follow_tail = False

    assert cli._handle_key(state, 360) is None
    assert state.scroll_offset == 30
    assert state.follow_tail is True
    assert state.input_text == "hello"
    assert state.error == ""


def test_alternate_page_up_integer_constants_scroll(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_PREVIOUS", 370, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_SPREVIOUS", 398, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 370) is None
    assert state.scroll_offset == 20
    assert state.input_text == "hello"
    assert state.error == ""

    assert cli._handle_key(state, 398) is None
    assert state.scroll_offset == 10
    assert state.input_text == "hello"
    assert state.error == ""


def test_alternate_page_down_integer_constants_scroll(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_NEXT", 367, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_SNEXT", 396, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"
    state.scroll_offset = 0
    state.chat_max_scroll = 30
    state.follow_tail = False

    assert cli._handle_key(state, 367) is None
    assert state.scroll_offset == 10
    assert state.follow_tail is False
    assert state.input_text == "hello"
    assert state.error == ""

    assert cli._handle_key(state, 396) is None
    assert state.scroll_offset == 20
    assert state.follow_tail is False
    assert state.input_text == "hello"
    assert state.error == ""


def test_unknown_non_ascii_integer_key_does_not_append_to_input_and_sets_error():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"

    assert cli._handle_key(state, 500) is None
    assert state.input_text == "hello"
    assert state.scroll_offset == 0
    assert state.error == "Key ignored: 500"


def test_normal_unicode_input_still_appends():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")

    assert cli._handle_key(state, "ä") is None
    assert state.input_text == "ä"
    assert state.input_cursor == 1
    assert state.scroll_offset == 0
    assert state.error == ""


def test_input_left_right_move_cursor(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.input_text = "abc"
    state.input_cursor = 3

    assert cli._handle_key(state, cli.curses.KEY_LEFT) is None
    assert state.input_cursor == 2
    assert state.error == ""

    assert cli._handle_key(state, cli.curses.KEY_RIGHT) is None
    assert state.input_cursor == 3
    assert state.error == ""


def test_input_left_right_clamp_cursor():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.input_text = "abc"

    state.input_cursor = 0
    assert cli._handle_key(state, cli.curses.KEY_LEFT) is None
    assert state.input_cursor == 0

    state.input_cursor = len(state.input_text)
    assert cli._handle_key(state, cli.curses.KEY_RIGHT) is None
    assert state.input_cursor == len(state.input_text)


def test_input_inserts_text_at_cursor():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.input_text = "abc"
    state.input_cursor = 1

    assert cli._handle_key(state, "X") is None

    assert state.input_text == "aXbc"
    assert state.input_cursor == 2


def test_backspace_deletes_before_cursor():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.input_text = "aXbc"
    state.input_cursor = 2

    assert cli._handle_key(state, 127) is None

    assert state.input_text == "abc"
    assert state.input_cursor == 1


def test_backspace_at_start_is_noop():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.input_text = "abc"
    state.input_cursor = 0

    assert cli._handle_key(state, 127) is None

    assert state.input_text == "abc"
    assert state.input_cursor == 0


def test_read_tui_key_combines_page_key_escape_sequences():
    from llmflask import cli

    class MockScreen:
        def __init__(self):
            self.keys = ["\x1b", "[", "5", "~"]
            self.nodelay_calls = []

        def get_wch(self):
            if not self.keys:
                raise cli.curses.error
            return self.keys.pop(0)

        def nodelay(self, enabled):
            self.nodelay_calls.append(enabled)

    screen = MockScreen()

    assert cli._read_tui_key(screen) == "\x1b[5~"
    assert screen.nodelay_calls == [True, False]


def test_read_tui_key_consumes_unknown_escape_sequence_without_polluting_input():
    from llmflask import cli
    from llmflask.cli import TuiState

    class MockScreen:
        def __init__(self):
            self.keys = ["\x1b", "[", "x", "~"]

        def get_wch(self):
            if not self.keys:
                raise cli.curses.error
            return self.keys.pop(0)

        def nodelay(self, enabled):
            pass

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"
    ch = cli._read_tui_key(MockScreen())

    assert ch == "\x1b"
    assert cli._handle_key(state, ch) is None
    assert state.input_text == "hello"


def test_page_keys_scroll_in_sessions_focus(monkeypatch):
    from llmflask import cli
    from llmflask.cli import FOCUS_SESSIONS, TuiState

    monkeypatch.setattr(cli.curses, "KEY_PPAGE", 339, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_NPAGE", 338, raising=False)

    state = TuiState("x", 1, "testuser")
    state.focus = FOCUS_SESSIONS
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 339) is None
    assert state.scroll_offset == 20

    assert cli._handle_key(state, 338) is None
    assert state.scroll_offset == 30


def test_draw_scroll_offset_zero_shows_newest_lines(monkeypatch):
    import curses
    from llmflask.cli import TuiState, draw

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)

    state = TuiState("x", 1, "testuser")
    state.current_session = 1
    state.messages = [{"role": "user", "content": f"line-{i:02d}"} for i in range(20)]

    class MockScreen:
        def __init__(self):
            self.chat_lines = []

        def getmaxyx(self):
            return (10, 80)

        def erase(self):
            pass

        def refresh(self):
            pass

        def addch(self, *a):
            pass

        def addstr(self, *args):
            if len(args) >= 3 and args[1] == 25 and 0 <= args[0] < 6:
                self.chat_lines.append(args[2])

        def hline(self, *a):
            pass

        def move(self, *a):
            pass

    screen = MockScreen()
    draw(screen, state)

    assert state.chat_max_scroll == 14
    assert state.scroll_offset == 14
    assert state.follow_tail is True
    rendered = "\n".join(screen.chat_lines)
    assert "line-19" in rendered
    assert "line-00" not in rendered


def test_draw_page_up_shows_older_lines_then_page_down_returns(monkeypatch):
    import curses
    from llmflask import cli
    from llmflask.cli import TuiState, draw

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)

    state = TuiState("x", 1, "testuser")
    state.current_session = 1
    state.messages = [{"role": "user", "content": f"line-{i:02d}"} for i in range(20)]
    state.chat_max_scroll = 14
    state.scroll_offset = 14
    cli._scroll_page_up(state)

    class MockScreen:
        def __init__(self):
            self.chat_lines = []

        def getmaxyx(self):
            return (10, 80)

        def erase(self):
            pass

        def refresh(self):
            pass

        def addch(self, *a):
            pass

        def addstr(self, *args):
            if len(args) >= 3 and args[1] == 25 and 0 <= args[0] < 6:
                self.chat_lines.append(args[2])

        def hline(self, *a):
            pass

        def move(self, *a):
            pass

    screen = MockScreen()
    draw(screen, state)

    rendered = "\n".join(screen.chat_lines)
    assert "line-04" in rendered
    assert "line-19" not in rendered
    assert state.scroll_offset == 4
    assert state.follow_tail is False

    cli._scroll_page_down(state)
    screen = MockScreen()
    draw(screen, state)
    rendered = "\n".join(screen.chat_lines)
    assert "line-19" in rendered
    assert state.scroll_offset == 14
    assert state.follow_tail is True


def test_page_keys_scroll_while_streaming(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_PPAGE", 339, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_NPAGE", 338, raising=False)

    state = TuiState("x", 1, "testuser")
    state.streaming = True
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 339) is None
    assert state.scroll_offset == 20
    assert state.follow_tail is False

    assert cli._handle_key(state, 338) is None
    assert state.scroll_offset == 30
    assert state.follow_tail is True


def test_arrow_keys_scroll_one_line_in_input_focus(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_UP", 259, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_DOWN", 258, raising=False)

    state = TuiState("x", 1, "testuser")
    state.scroll_offset = 10
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 259) is None
    assert state.scroll_offset == 9
    assert state.follow_tail is False

    assert cli._handle_key(state, 258) is None
    assert state.scroll_offset == 10
    assert state.follow_tail is False


def test_arrow_down_reenables_follow_tail_at_bottom(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_DOWN", 258, raising=False)

    state = TuiState("x", 1, "testuser")
    state.scroll_offset = 29
    state.chat_max_scroll = 30
    state.follow_tail = False

    assert cli._handle_key(state, 258) is None
    assert state.scroll_offset == 30
    assert state.follow_tail is True


def test_arrow_keys_still_navigate_sessions(monkeypatch):
    from llmflask import cli
    from llmflask.cli import FOCUS_SESSIONS, TuiState

    monkeypatch.setattr(cli.curses, "KEY_UP", 259, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_DOWN", 258, raising=False)

    state = TuiState("x", 1, "testuser")
    state.focus = FOCUS_SESSIONS
    state.sessions = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
    state.session_idx = 0
    state.scroll_offset = 10
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 258) is None
    assert state.session_idx == 1
    assert state.scroll_offset == 10

    assert cli._handle_key(state, 259) is None
    assert state.session_idx == 0
    assert state.scroll_offset == 10


def test_arrow_keys_scroll_while_streaming(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli.curses, "KEY_UP", 259, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_DOWN", 258, raising=False)

    state = TuiState("x", 1, "testuser")
    state.streaming = True
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 259) is None
    assert state.scroll_offset == 29
    assert state.follow_tail is False

    assert cli._handle_key(state, 258) is None
    assert state.scroll_offset == 30
    assert state.follow_tail is True


def test_streaming_ignores_text_but_ctrl_c_still_quits():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.streaming = True
    state.input_text = "hello"

    assert cli._handle_key(state, "a") is None
    assert state.input_text == "hello"

    assert cli._handle_key(state, 3) == "quit"
    assert state.input_text == "hello"


def test_draw_streaming_preserves_nonzero_scroll_offset(monkeypatch):
    import curses
    from llmflask.cli import TuiState, draw

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)

    state = TuiState("x", 1, "testuser")
    state.current_session = 1
    state.messages = [{"role": "user", "content": f"line-{i:02d}"} for i in range(20)]
    state.streaming = True
    state.streamed_response = "streaming-tail"
    state.scroll_offset = 4
    state.follow_tail = False

    class MockScreen:
        def __init__(self):
            self.chat_lines = []

        def getmaxyx(self):
            return (10, 80)

        def erase(self):
            pass

        def refresh(self):
            pass

        def addch(self, *a):
            pass

        def addstr(self, *args):
            if len(args) >= 3 and args[1] == 25 and 0 <= args[0] < 6:
                self.chat_lines.append(args[2])

        def hline(self, *a):
            pass

        def move(self, *a):
            pass

    screen = MockScreen()
    draw(screen, state)

    assert state.chat_max_scroll == 15
    assert state.scroll_offset == 4
    assert state.follow_tail is False
    rendered = "\n".join(screen.chat_lines)
    assert "line-19" not in rendered
    assert "streaming-tail" not in rendered


def test_draw_streaming_at_bottom_shows_streamed_tail(monkeypatch):
    import curses
    from llmflask.cli import TuiState, draw

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)

    state = TuiState("x", 1, "testuser")
    state.current_session = 1
    state.messages = [{"role": "user", "content": f"line-{i:02d}"} for i in range(6)]
    state.streaming = True
    state.streamed_response = "streaming-tail"
    state.scroll_offset = 0

    class MockScreen:
        def __init__(self):
            self.chat_lines = []

        def getmaxyx(self):
            return (10, 80)

        def erase(self):
            pass

        def refresh(self):
            pass

        def addch(self, *a):
            pass

        def addstr(self, *args):
            if len(args) >= 3 and args[1] == 25 and 0 <= args[0] < 6:
                self.chat_lines.append(args[2])

        def hline(self, *a):
            pass

        def move(self, *a):
            pass

    screen = MockScreen()
    draw(screen, state)

    assert state.chat_max_scroll == 1
    assert state.scroll_offset == 1
    assert state.follow_tail is True
    assert "streaming-tail" in "\n".join(screen.chat_lines)


def test_draw_positions_input_cursor(monkeypatch):
    import curses
    from llmflask.cli import TuiState, draw

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "abcdef"
    state.input_cursor = 2

    class MockScreen:
        def __init__(self):
            self.moves = []

        def getmaxyx(self):
            return (10, 80)

        def erase(self):
            pass

        def refresh(self):
            pass

        def addch(self, *a):
            pass

        def addstr(self, *a):
            pass

        def hline(self, *a):
            pass

        def move(self, *args):
            self.moves.append(args)

    screen = MockScreen()
    draw(screen, state)

    assert screen.moves[-1] == (9, 4)


def test_draw_keeps_long_input_cursor_visible(monkeypatch):
    import curses
    from llmflask.cli import TuiState, draw

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)

    state = TuiState("x", 1, "testuser")
    state.input_text = "abcdefghijklmnopqrstuvwxyz0123456789ABCD"
    state.input_cursor = len(state.input_text)

    class MockScreen:
        def __init__(self):
            self.moves = []
            self.input_line = ""

        def getmaxyx(self):
            return (10, 30)

        def erase(self):
            pass

        def refresh(self):
            pass

        def addch(self, *a):
            pass

        def addstr(self, *args):
            if len(args) >= 3 and args[0] == 9:
                self.input_line = args[2]

        def hline(self, *a):
            pass

        def move(self, *args):
            self.moves.append(args)

    screen = MockScreen()
    draw(screen, state)

    assert screen.input_line == "> nopqrstuvwxyz0123456789ABCD"
    assert screen.moves[-1] == (9, 29)


def test_tui_trace_path_uses_tmp_and_safe_user(monkeypatch):
    import os
    from llmflask import cli

    monkeypatch.setenv("USER", "Alice Smith/../x")

    path = cli._tui_trace_path()

    assert path.startswith("/tmp/llmflask-tui-trace-")
    assert path.endswith(".log")
    assert " " not in os.path.basename(path)
    assert "/" not in os.path.basename(path)


def test_trace_event_writes_json_line(monkeypatch, tmp_path):
    import json
    from llmflask import cli
    from llmflask.cli import TuiState

    trace_path = tmp_path / "trace.log"
    monkeypatch.setattr(cli, "_tui_trace_path", lambda: str(trace_path))
    state = TuiState("x", 1, "testuser")
    state.trace_enabled = True
    state.scroll_offset = 7

    cli._trace_event("test_event", state, foo="bar")

    payload = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "test_event"
    assert payload["tui_user"] == "testuser"
    assert payload["foo"] == "bar"
    assert payload["scroll_offset"] == 7


def test_trace_event_default_is_noop(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.cli import TuiState

    trace_path = tmp_path / "trace.log"
    monkeypatch.setattr(cli, "_tui_trace_path", lambda: str(trace_path))

    cli._trace_event("test_event", TuiState("x", 1, "testuser"))

    assert not trace_path.exists()


def test_trace_event_swallows_write_errors(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli, "_tui_trace_path", lambda: "/tmp/does-not-exist-for-llmflask/trace.log")

    state = TuiState("x", 1, "testuser")
    state.trace_enabled = True

    cli._trace_event("test_event", state)


def test_handle_key_traces_page_actions(monkeypatch, tmp_path):
    import json
    from llmflask import cli
    from llmflask.cli import TuiState

    trace_path = tmp_path / "trace.log"
    monkeypatch.setattr(cli, "_tui_trace_path", lambda: str(trace_path))
    monkeypatch.setattr(cli.curses, "KEY_PPAGE", 339, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_NPAGE", 338, raising=False)
    state = TuiState("x", 1, "testuser")
    state.trace_enabled = True
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 339) is None
    assert cli._handle_key(state, 338) is None

    actions = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert [entry["action"] for entry in actions] == ["page_up", "page_down"]
    assert [entry["key_name"] for entry in actions] == ["KEY_PPAGE", "KEY_NPAGE"]
    assert actions[0]["before_scroll_offset"] == 30
    assert actions[0]["scroll_offset"] == 20
    assert actions[1]["before_scroll_offset"] == 20
    assert actions[1]["scroll_offset"] == 30


def test_handle_key_traces_home_and_end_actions(monkeypatch, tmp_path):
    import json
    from llmflask import cli
    from llmflask.cli import TuiState

    trace_path = tmp_path / "trace.log"
    monkeypatch.setattr(cli, "_tui_trace_path", lambda: str(trace_path))
    monkeypatch.setattr(cli.curses, "KEY_HOME", 262, raising=False)
    monkeypatch.setattr(cli.curses, "KEY_END", 360, raising=False)
    state = TuiState("x", 1, "testuser")
    state.trace_enabled = True
    state.scroll_offset = 30
    state.chat_max_scroll = 30

    assert cli._handle_key(state, 262) is None
    assert cli._handle_key(state, 360) is None

    actions = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert [entry["action"] for entry in actions] == ["home", "end"]
    assert [entry["key_name"] for entry in actions] == ["KEY_HOME", "KEY_END"]
    assert actions[0]["scroll_offset"] == 0
    assert actions[1]["scroll_offset"] == 30


def test_draw_trace_excludes_message_content(monkeypatch, tmp_path):
    import curses
    import json
    from llmflask import cli
    from llmflask.cli import TuiState, draw

    monkeypatch.setattr(curses, "ACS_VLINE", 0, raising=False)
    monkeypatch.setattr(curses, "ACS_HLINE", 0, raising=False)
    monkeypatch.setattr(curses, "A_NORMAL", 0, raising=False)
    monkeypatch.setattr(curses, "A_BOLD", 0, raising=False)
    monkeypatch.setattr(curses, "A_REVERSE", 0, raising=False)
    trace_path = tmp_path / "trace.log"
    monkeypatch.setattr(cli, "_tui_trace_path", lambda: str(trace_path))

    state = TuiState("x", 1, "testuser")
    state.trace_enabled = True
    state.current_session = 1
    state.messages = [{"role": "user", "content": "SECRET-CONTENT"}]

    class MockScreen:
        def getmaxyx(self):
            return (10, 80)

        def erase(self):
            pass

        def refresh(self):
            pass

        def addch(self, *a):
            pass

        def addstr(self, *a):
            pass

        def hline(self, *a):
            pass

        def move(self, *a):
            pass

    draw(MockScreen(), state)

    raw = trace_path.read_text(encoding="utf-8")
    payload = json.loads(raw.splitlines()[0])
    assert "SECRET-CONTENT" not in raw
    assert payload["event"] == "draw"
    assert payload["wrapped_lines"] == 1


def test_ctrl_c_quits_without_mutating_input():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("x", 1, "testuser")
    state.input_text = "hello"

    assert cli._handle_key(state, 3) == "quit"
    assert state.input_text == "hello"


def test_restore_terminal_is_defensive(monkeypatch):
    from llmflask import cli

    calls = []

    def fail():
        calls.append("cleanup")
        raise RuntimeError("not initialized")

    monkeypatch.setattr(cli.curses, "nocbreak", fail)
    monkeypatch.setattr(cli.curses, "echo", fail)
    monkeypatch.setattr(cli.curses, "endwin", fail)
    monkeypatch.setattr(cli.os, "system", lambda cmd: calls.append(cmd) or 0)

    cli._restore_terminal()

    assert calls.count("cleanup") == 3
    assert "stty sane" in calls[-1]


def test_restore_terminal_swallows_keyboard_interrupt(monkeypatch):
    from llmflask import cli

    calls = []

    def interrupt():
        calls.append("interrupt")
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.curses, "nocbreak", interrupt)
    monkeypatch.setattr(cli.curses, "echo", interrupt)
    monkeypatch.setattr(cli.curses, "endwin", interrupt)
    monkeypatch.setattr(cli.os, "system", lambda cmd: calls.append(cmd) or 0)

    cli._restore_terminal()

    assert calls.count("interrupt") == 3
    assert "stty sane" in calls[-1]


def test_run_curses_cleans_up_when_main_loop_interrupts(monkeypatch):
    from llmflask import cli

    calls = []

    class MockScreen:
        def keypad(self, enabled):
            calls.append(("keypad", enabled))

    monkeypatch.setattr(cli.curses, "initscr", lambda: MockScreen())
    monkeypatch.setattr(cli.curses, "noecho", lambda: calls.append("noecho"))
    monkeypatch.setattr(cli.curses, "cbreak", lambda: calls.append("cbreak"))
    monkeypatch.setattr(cli.curses, "start_color", lambda: calls.append("start_color"))
    monkeypatch.setattr(cli, "_restore_terminal", lambda: calls.append("restore"))

    def main_loop(stdscr):
        calls.append("main")
        raise KeyboardInterrupt

    try:
        cli._run_curses(main_loop)
    except KeyboardInterrupt:
        pass

    assert calls == [
        "noecho",
        "cbreak",
        ("keypad", True),
        "start_color",
        "main",
        ("keypad", False),
        "restore",
    ]


def test_run_tui_treats_run_curses_keyboard_interrupt_as_normal(monkeypatch):
    from llmflask import cli

    calls = []

    monkeypatch.setattr(cli, "_setup_locale", lambda: calls.append("locale"))
    monkeypatch.setattr(cli.os, "system", lambda cmd: calls.append(cmd) or 0)

    def interrupt(main_loop):
        calls.append("run_curses")
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run_curses", interrupt)

    cli.run_tui("127.0.0.1", 5000, "testuser")

    assert calls[0] == "locale"
    assert "stty -ixon" in calls[1]
    assert calls[-1] == "run_curses"


def test_switch_session_uses_user_query(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    seen = {}

    def fake_get(url, *args):
        seen["url"] = url
        return []

    monkeypatch.setattr(cli, "_api_get", fake_get)

    state = TuiState("127.0.0.1", 5000, "Alice Smith")
    cli._switch_session(state, 7)

    assert seen["url"] == "http://127.0.0.1:5000/api/chat/7/messages?user=Alice+Smith"
    assert state.current_session == 7


def test_delete_session_uses_user_query(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    seen = {}

    def fake_delete(url, *args):
        seen["url"] = url
        return True

    monkeypatch.setattr(cli, "_api_delete", fake_delete)
    monkeypatch.setattr(cli, "_load_sessions", lambda state: None)

    state = TuiState("127.0.0.1", 5000, "Alice Smith")
    state.sessions = [{"id": 7, "title": "Chat"}]
    cli._delete_session(state)

    assert seen["url"] == "http://127.0.0.1:5000/api/sessions/7?user=Alice+Smith"


def test_open_initial_session_keeps_empty_profile_empty(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    switched = []
    monkeypatch.setattr(cli, "_switch_session", lambda state, sid: switched.append(sid))

    state = TuiState("127.0.0.1", 5000, "alice")
    state.sessions = []

    cli._open_initial_session(state)

    assert state.current_session is None
    assert state.messages == []
    assert switched == []


def test_open_initial_session_switches_first_session(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    switched = []
    monkeypatch.setattr(cli, "_switch_session", lambda state, sid: switched.append(sid))

    state = TuiState("127.0.0.1", 5000, "alice")
    state.sessions = [{"id": 4, "title": "A"}]

    cli._open_initial_session(state)

    assert state.current_session == 4
    assert switched == [4]


def test_send_without_session_sets_error():
    from llmflask.cli import TuiState, _send_message

    state = TuiState("127.0.0.1", 5000, "alice")
    state.input_text = "hello"

    _send_message(state)

    assert "Ctrl+N" in state.error
    assert state.input_text == "hello"


def test_send_without_model_sets_error():
    from llmflask.cli import TuiState, _send_message

    state = TuiState("127.0.0.1", 5000, "alice")
    state.current_session = 1
    state.input_text = "hello"

    _send_message(state)

    assert "No model" in state.error
    assert state.input_text == "hello"


def test_server_send_message_sends_system_prompt(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState, _send_message

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
        def start(self):
            self.target()

    class MockResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def raise_for_status(self):
            pass

        def iter_lines(self):
            yield 'data: {"token": "ok\\n", "done": false}'
            yield 'data: {"token": "", "done": true}'

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def stream(self, method, url, headers=None, json=None):
            seen["method"] = method
            seen["url"] = url
            seen["headers"] = headers
            seen["json"] = json
            return MockResponse()

    seen = {}
    monkeypatch.setattr(cli.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(cli.httpx, "Client", MockClient)
    monkeypatch.setattr(cli, "_load_sessions", lambda state: None)
    state = TuiState("127.0.0.1", 5000, "alice", system_prompt="Systemprompt")
    state.current_session = 7
    state.current_model = "llama3"
    state.input_text = "hi"

    _send_message(state)

    assert seen["url"] == "http://127.0.0.1:5000/api/chat?user=alice"
    assert seen["headers"] == {"X-LLMFlask-Request": "1"}
    assert seen["json"] == {
        "session_id": 7,
        "message": "hi",
        "model": "llama3",
        "search": False,
        "system_prompt": "Systemprompt",
    }
    assert state.messages == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "ok\n"},
    ]


def test_direct_load_models_requires_provider_key(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.setattr(cli, "load_api_keys", lambda: {})

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")

    cli._load_models(state)

    assert state.models == []
    assert "API key is not set" in state.error


def test_direct_load_models_uses_selected_provider(monkeypatch):
    from llmflask import cli
    from llmflask.cli import TuiState

    seen = {}

    def fake_list_remote_models(provider, api_key):
        seen["provider"] = provider.name
        seen["api_key"] = api_key
        return [{"name": "deepseek/deepseek-chat", "label": "DeepSeek: deepseek-chat"}]

    monkeypatch.setattr(cli, "load_api_keys", lambda: {"DEEPSEEK_API_KEY": "secret"})
    monkeypatch.setattr(cli, "list_remote_models", fake_list_remote_models)

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")

    cli._load_models(state)

    assert seen == {"provider": "deepseek", "api_key": "secret"}
    assert state.current_model == "deepseek/deepseek-chat"


def test_direct_load_sessions_uses_local_sqlite(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.database import create_session, init_db
    from llmflask.cli import TuiState

    db_path = tmp_path / "direct-chat.db"
    monkeypatch.setattr(cli, "DATABASE", str(db_path))
    init_db(str(db_path))
    create_session(str(db_path), user="alice", title="Local A", model="openai/gpt-4.1")

    state = TuiState("127.0.0.1", 5000, "alice", "openai")
    cli._ensure_user(state)
    cli._load_sessions(state)

    assert [session["title"] for session in state.sessions] == ["Local A"]
    assert state.current_session is None


def test_direct_new_session_creates_local_history(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.database import get_sessions, init_db
    from llmflask.cli import TuiState

    db_path = tmp_path / "direct-chat.db"
    monkeypatch.setattr(cli, "DATABASE", str(db_path))
    init_db(str(db_path))
    state = TuiState("127.0.0.1", 5000, "alice", "openai")
    state.messages = [{"role": "user", "content": "old"}]
    state.current_model = "openai/gpt-4.1"

    cli._new_session(state)

    assert state.current_session is not None
    assert state.messages == []
    sessions = get_sessions(str(db_path), "alice")
    assert len(sessions) == 1
    assert sessions[0]["title"] == "Direct: OpenAI"
    assert sessions[0]["model"] == "openai/gpt-4.1"


def test_tui_markdown_export_writes_current_chat_to_cwd(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.chdir(tmp_path)
    state = TuiState("127.0.0.1", 5000, "alice")
    state.current_session = 12
    state.sessions = [{"id": 12, "title": "My Chat"}]
    state.messages = [{"role": "user", "content": "copy this"}]

    cli._export_markdown_file(state)

    exported = tmp_path / "llmflask-chat-12-My-Chat.md"
    assert exported.exists()
    assert "copy this" in exported.read_text(encoding="utf-8")
    assert str(exported) in state.error


def test_tui_markdown_export_sanitizes_and_does_not_overwrite(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "llmflask-chat-7-A-B.md"
    existing.write_text("old", encoding="utf-8")
    state = TuiState("127.0.0.1", 5000, "alice")
    state.current_session = 7
    state.sessions = [{"id": 7, "title": "A / B"}]
    state.messages = [{"role": "assistant", "content": "new"}]

    cli._export_markdown_file(state)

    exported = tmp_path / "llmflask-chat-7-A-B-2.md"
    assert existing.read_text(encoding="utf-8") == "old"
    assert "new" in exported.read_text(encoding="utf-8")
    assert str(exported) in state.error


def test_tui_markdown_export_handles_empty_chat(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.chdir(tmp_path)
    state = TuiState("127.0.0.1", 5000, "alice")

    cli._export_markdown_file(state)

    assert list(tmp_path.iterdir()) == []
    assert "No active chat" in state.error


def test_tui_markdown_export_works_in_direct_mode(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.cli import TuiState

    monkeypatch.chdir(tmp_path)
    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")
    state.current_session = 3
    state.sessions = [{"id": 3, "title": "Direct: DeepSeek"}]
    state.messages = [{"role": "assistant", "content": "direct copy"}]

    cli._export_url(state)

    exported = tmp_path / "llmflask-chat-3-Direct-DeepSeek.md"
    assert exported.exists()
    assert "direct copy" in exported.read_text(encoding="utf-8")


def test_direct_disabled_actions_show_clear_errors():
    from llmflask import cli
    from llmflask.cli import TuiState

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")

    state.search_enabled = True
    cli._toggle_search(state)
    assert state.search_enabled is False
    assert "Search" in state.error


def test_direct_delete_session_removes_local_sqlite_session(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.database import create_session, get_sessions, init_db
    from llmflask.cli import TuiState

    db_path = tmp_path / "direct-chat.db"
    monkeypatch.setattr(cli, "DATABASE", str(db_path))
    init_db(str(db_path))
    sid = create_session(str(db_path), user="alice", title="Delete me", model="deepseek/deepseek-chat")

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")
    state.sessions = [{"id": sid, "title": "Delete me"}]
    state.current_session = sid

    cli._delete_session(state)

    assert get_sessions(str(db_path), "alice") == []
    assert state.current_session is None
    assert state.messages == []


def test_direct_switch_session_loads_local_messages(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.database import add_message, create_session, init_db
    from llmflask.cli import TuiState

    db_path = tmp_path / "direct-chat.db"
    monkeypatch.setattr(cli, "DATABASE", str(db_path))
    init_db(str(db_path))
    sid = create_session(str(db_path), user="alice", title="Local", model="deepseek/deepseek-chat")
    add_message(str(db_path), sid, "user", "hi")
    add_message(str(db_path), sid, "assistant", "hello")

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")

    cli._switch_session(state, sid)

    assert state.current_session == sid
    assert [message["content"] for message in state.messages] == ["hi", "hello"]


def test_direct_send_message_streams_without_server(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.database import create_session, get_messages, get_sessions, init_db
    from llmflask.cli import TuiState, _send_message

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
        def start(self):
            self.target()

    seen = {}

    def fake_chat_stream(messages, model):
        seen["messages"] = list(messages)
        seen["model"] = model
        yield "hello"
        yield " world"

    monkeypatch.setattr(cli.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(cli, "chat_stream", fake_chat_stream)
    db_path = tmp_path / "direct-chat.db"
    monkeypatch.setattr(cli, "DATABASE", str(db_path))
    init_db(str(db_path))
    sid = create_session(str(db_path), user="alice", title="Direct: DeepSeek", model="deepseek/deepseek-chat")

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")
    state.current_session = sid
    state.current_model = "deepseek/deepseek-chat"
    state.input_text = "hi"
    state.input_cursor = 2

    _send_message(state)

    assert seen["model"] == "deepseek/deepseek-chat"
    assert seen["messages"] == [{"role": "user", "content": "hi"}]
    assert [(message["role"], message["content"]) for message in state.messages] == [
        ("user", "hi"),
        ("assistant", "hello world\n"),
    ]
    assert [(message["role"], message["content"]) for message in get_messages(str(db_path), sid)] == [
        ("user", "hi"),
        ("assistant", "hello world\n"),
    ]


class TestCliValidation:
    """Test that CLI rejects invalid flag combinations."""
    def _run(self, argv, monkeypatch):
        import sys
        from llmflask.__main__ import main
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc:
            main()
        return exc.value.code

    def test_no_args_shows_help(self, monkeypatch, capsys):
        import sys
        from llmflask.__main__ import main
        monkeypatch.setattr(sys, "argv", ["llmflask"])
        assert main() == 0
        assert "Quick Start" in capsys.readouterr().out

    def test_server_tui_mutual(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--server", "--tui"], monkeypatch) == 2
        assert "different modes" in capsys.readouterr().err

    def test_server_cmd_mutual(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--server", "--cmd", "--text", "q", "--model", "m"], monkeypatch) == 2
        assert "different modes" in capsys.readouterr().err

    def test_configure_api_keys_mode(self, monkeypatch):
        import sys
        from llmflask import __main__ as cli_main

        monkeypatch.setattr(sys, "argv", ["llmflask", "--configure-api-keys"])
        monkeypatch.setattr(cli_main, "configure_api_keys", lambda: 9)

        assert cli_main.main() == 9

    def test_configure_api_keys_is_exclusive(self, monkeypatch, capsys):
        assert self._run(
            ["llmflask", "--configure-api-keys", "--models"], monkeypatch
        ) == 2
        assert "different modes" in capsys.readouterr().err

    def test_usepool_cmd_mutual(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--usepool", "--file", "f", "--text", "r", "--cmd", "--text", "q", "--model", "m"], monkeypatch) == 2
        assert "different modes" in capsys.readouterr().err

    def test_tui_trace_needs_tui(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--tui-trace"], monkeypatch) == 2
        assert "requires --tui" in capsys.readouterr().err

    def test_result_dir_needs_usepool(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--result-dir", "/tmp"], monkeypatch) == 2
        assert "only valid with --usepool" in capsys.readouterr().err

    def test_pool_name_needs_usepool(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--name", "test"], monkeypatch) == 2
        assert "only valid with --usepool" in capsys.readouterr().err

    def test_no_mode_errors(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--host", "x"], monkeypatch) == 2
        assert "No mode selected" in capsys.readouterr().err

    def test_server_without_value_dev(self, monkeypatch):
        import sys, types
        from llmflask.__main__ import main

        calls = []
        fake_app = types.ModuleType("llmflask.app")
        fake_app.create_app = lambda **kw: type("A", (), {"run": lambda s, **kw: calls.append(kw)})()
        monkeypatch.setitem(sys.modules, "llmflask.app", fake_app)
        monkeypatch.setattr("llmflask.__main__._verify_server_requirements", lambda: True)
        monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--host", "0", "--port", "5"])

        main()
        assert calls == [{"host": "0", "port": 5, "debug": False, "threaded": True}]

    def test_server_production(self, monkeypatch):
        import sys
        from llmflask import __main__ as cli_main

        calls = []
        def fake_gunicorn(app, host, port):
            calls.append(("gunicorn", host, port))

        monkeypatch.setattr(cli_main, "run_gunicorn", fake_gunicorn)
        monkeypatch.setattr("llmflask.app.create_app", lambda **kw: "app")
        monkeypatch.setattr(cli_main, "_verify_server_requirements", lambda: True)
        monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "production", "--host", "0", "--port", "5"])

        cli_main.main()
        assert calls == [("gunicorn", "0", 5)]

    def test_text_requires_cmd(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--server", "--text", "hi"], monkeypatch) == 2
        assert "--text requires --cmd" in capsys.readouterr().err

    def test_session_requires_cmd(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--server", "--session", "42"], monkeypatch) == 2
        assert "--session requires --cmd" in capsys.readouterr().err

    def test_provider_needs_tui_or_cmd(self, monkeypatch, capsys):
        assert self._run(["llmflask", "--server", "--provider", "deepseek"], monkeypatch) == 2
        assert "--provider requires" in capsys.readouterr().err

    def test_listen_host_conflict_rejected(self, monkeypatch, capsys):
        assert self._run(
            ["llmflask", "--server", "--listen", "0.0.0.0", "--host", "x"],
            monkeypatch,
        ) == 2
        assert "cannot be combined" in capsys.readouterr().err

    def test_listen_flag_starts_server(self, monkeypatch):
        import sys, types
        from llmflask.__main__ import main

        calls = []
        fake_app = types.ModuleType("llmflask.app")
        fake_app.create_app = lambda **kw: type("A", (), {"run": lambda s, **kw2: calls.append(kw2)})()
        monkeypatch.setitem(sys.modules, "llmflask.app", fake_app)
        monkeypatch.setattr("llmflask.__main__._verify_server_requirements", lambda: True)
        monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--listen", "0.0.0.0", "--port", "5050"])

        main()
        assert calls == [{"host": "0.0.0.0", "port": 5050, "debug": False, "threaded": True}]

    def test_listen_flag_with_production(self, monkeypatch):
        import sys
        from llmflask import __main__ as cli_main

        calls = []
        def fake_gunicorn(app, host, port):
            calls.append(("gunicorn", host, port))

        monkeypatch.setattr(cli_main, "run_gunicorn", fake_gunicorn)
        monkeypatch.setattr("llmflask.app.create_app", lambda **kw: "app")
        monkeypatch.setattr(cli_main, "_verify_server_requirements", lambda: True)
        monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "production", "--listen", "0.0.0.0", "--port", "5050"])

        cli_main.main()
        assert calls == [("gunicorn", "0.0.0.0", 5050)]

    def test_listen_default_is_loopback(self, monkeypatch):
        import sys, types
        from llmflask.__main__ import main

        calls = []
        fake_app = types.ModuleType("llmflask.app")
        fake_app.create_app = lambda **kw: type("A", (), {"run": lambda s, **kw2: calls.append(kw2)})()
        monkeypatch.setitem(sys.modules, "llmflask.app", fake_app)
        monkeypatch.setattr("llmflask.__main__._verify_server_requirements", lambda: True)
        monkeypatch.setattr(sys, "argv", ["llmflask", "--server"])

        main()
        assert calls == [{"host": "127.0.0.1", "port": 5000, "debug": False, "threaded": True}]

    def test_host_flag_still_works_for_server_compat(self, monkeypatch):
        import sys, types
        from llmflask.__main__ import main

        calls = []
        fake_app = types.ModuleType("llmflask.app")
        fake_app.create_app = lambda **kw: type("A", (), {"run": lambda s, **kw2: calls.append(kw2)})()
        monkeypatch.setitem(sys.modules, "llmflask.app", fake_app)
        monkeypatch.setattr("llmflask.__main__._verify_server_requirements", lambda: True)
        monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--host", "0.0.0.0", "--port", "5050"])

        main()
        assert calls == [{"host": "0.0.0.0", "port": 5050, "debug": False, "threaded": True}]

    def test_invalid_trusted_host_has_no_traceback(self, monkeypatch, capsys):
        import sys
        from llmflask import __main__ as cli_main

        monkeypatch.setattr(cli_main, "_verify_server_requirements", lambda: True)
        monkeypatch.setattr(
            "llmflask.app.create_app",
            lambda **kw: (_ for _ in ()).throw(
                ValueError("Invalid --trusted-host entry 'https://bad.example'")
            ),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "llmflask",
                "--server",
                "--trusted-host",
                "https://bad.example",
            ],
        )

        assert cli_main.main() == 2
        error = capsys.readouterr().err
        assert "Invalid --trusted-host" in error
        assert "--trusted-host llmflask.internal" in error
        assert "Traceback" not in error


def test_non_loopback_hostname_prints_startup_warning(monkeypatch, capsys):
    import socket
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.20", 0))
        ],
    )

    cli_main._print_startup_banner("llmflask.internal", 5000)

    error = capsys.readouterr().err
    assert "No authentication" in error
    assert "llmflask.internal:5000" in error


def test_wildcard_ip_discovery_suppresses_hostname_stderr(monkeypatch):
    import socket
    import subprocess
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("0.0.0.0", 0))
        ],
    )
    calls = []

    def fake_check_output(command, **kwargs):
        calls.append((command, kwargs))
        return "192.0.2.20\n"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    cli_main._print_startup_banner("0.0.0.0", 5000)

    assert calls == [
        (
            ["hostname", "-I"],
            {
                "text": True,
                "timeout": 2,
                "stderr": subprocess.DEVNULL,
            },
        )
    ]


def test_usepool_parses_source_and_request(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_cli(source, request_text, model_ref, host, port, pool_name=None, reuse=False, result_dir=None):
        calls.append((source, request_text, model_ref, host, port, pool_name, reuse))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_cli", fake_run_pool_cli)
    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    monkeypatch.setattr(cli_main, "DEFAULT_RESULT_DIR", None)
    monkeypatch.setattr(sys, "argv", [
        "llmflask", "--usepool", "--file", "./test.csv", "--text", "Analysiere",
        "--model", "ollama/qwen3:8b", "--host", "192.0.2.100",
    ])

    assert cli_main.main() == 0
    assert calls == [("./test.csv", "Analysiere", "ollama/qwen3:8b", "192.0.2.100", 5000, None, False)]


def test_usepool_with_model_flag(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_cli(source, request_text, model_ref, host, port, pool_name=None, reuse=False, result_dir=None):
        calls.append((source, request_text, model_ref, host, port, pool_name, reuse))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_cli", fake_run_pool_cli)
    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    monkeypatch.setattr(cli_main, "DEFAULT_RESULT_DIR", None)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--usepool", "--file", "./data", "--text", "Frage", "--model", "qwen3:14b"])

    assert cli_main.main() == 0
    assert calls == [("./data", "Frage", "qwen3:14b", "127.0.0.1", 5000, None, False)]


def test_usepool_with_pool_name_and_reuse(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_cli(source, request_text, model_ref, host, port, pool_name=None, reuse=False, result_dir=None):
        calls.append((source, request_text, model_ref, host, port, pool_name, reuse))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_cli", fake_run_pool_cli)
    monkeypatch.setattr(cli_main, "_validate_model_ref", lambda *a, **kw: True)
    monkeypatch.setattr(cli_main, "DEFAULT_RESULT_DIR", None)
    monkeypatch.setattr(sys, "argv", [
        "llmflask", "--usepool", "--file", "./data", "--text", "Frage",
        "--name", "my-pool", "--reuse-pool", "--model", "ollama/qwen3:8b",
    ])

    assert cli_main.main() == 0
    assert calls == [("./data", "Frage", "ollama/qwen3:8b", "127.0.0.1", 5000, "my-pool", True)]


def test_pool_list_command(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_command(args, host, port):
        calls.append((args.pool_action, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_command", fake_run_pool_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "pool", "list"])

    assert cli_main.main() == 0
    assert calls == [("list", "127.0.0.1", 5000)]


def test_pool_show_command(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_command(args, host, port):
        calls.append((args.pool_action, args.name, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_command", fake_run_pool_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "pool", "show", "my-pool"])

    assert cli_main.main() == 0
    assert calls == [("show", "my-pool", "127.0.0.1", 5000)]


def test_pool_run_command(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_command(args, host, port):
        calls.append((args.pool_action, args.name, args.model, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_command", fake_run_pool_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--model", "qwen3:14b", "pool", "run", "my-pool"])

    assert cli_main.main() == 0
    assert calls == [("run", "my-pool", "qwen3:14b", "127.0.0.1", 5000)]


def test_pool_pack_command(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_command(args, host, port):
        calls.append((args.pool_action, args.name, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_command", fake_run_pool_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "pool", "pack", "my-pool"])

    assert cli_main.main() == 0
    assert calls == [("pack", "my-pool", "127.0.0.1", 5000)]


def test_pool_remove_command(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_command(args, host, port):
        calls.append((args.pool_action, args.name, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_command", fake_run_pool_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "pool", "remove", "my-pool"])

    assert cli_main.main() == 0
    assert calls == [("remove", "my-pool", "127.0.0.1", 5000)]


def test_pool_remove_all_command(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_command(args, host, port):
        calls.append((args.pool_action, args.name, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_command", fake_run_pool_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "pool", "remove", "all"])

    assert cli_main.main() == 0
    assert calls == [("remove", "all", "127.0.0.1", 5000)]


def test_pool_remove_requires_explicit_target(monkeypatch):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_run_pool_command(args, host, port):
        calls.append((args.pool_action, args.name, host, port))
        return 0

    monkeypatch.setattr(cli_main, "_run_pool_command", fake_run_pool_command)
    monkeypatch.setattr(sys, "argv", ["llmflask", "pool", "remove"])

    with pytest.raises(SystemExit) as error:
        cli_main.main()
    assert error.value.code == 2
    assert calls == []


def test_server_without_value_defaults_dev(monkeypatch):
    import sys
    from llmflask.__main__ import main

    calls = []

    def fake_app_run(self, **kwargs):
        calls.append(kwargs)

    def fake_create_app(**kw):
        return type("FakeApp", (), {"run": fake_app_run})()

    monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--host", "0.0.0.0", "--port", "5050"])
    monkeypatch.setattr("llmflask.__main__._verify_server_requirements", lambda: True)
    monkeypatch.setattr("llmflask.app.create_app", fake_create_app)

    main()
    assert calls == [{"host": "0.0.0.0", "port": 5050, "debug": False, "threaded": True}]


def test_server_blocks_when_ollama_unreachable(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    def fake_create_app(**kw):
        calls.append("create_app")
        return None

    monkeypatch.setattr("llmflask.app.create_app", fake_create_app)
    monkeypatch.setattr(cli_main, "ollama_reachable", lambda: False)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--host", "0.0.0.0", "--port", "5050"])

    result = cli_main.main()

    assert result == 2
    assert calls == []
    err = capsys.readouterr().err
    assert "Ollama is required but not reachable" in err
    assert "make install-ai" in err
    assert "systemctl start ollama" in err


def test_server_starts_when_ollama_reachable(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    class FakeApp:
        def run(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr("llmflask.app.create_app", lambda **kw: FakeApp())
    monkeypatch.setattr(cli_main, "ollama_reachable", lambda: True)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--host", "0.0.0.0", "--port", "5050"])

    result = cli_main.main()

    assert result == 0
    assert calls == [{"host": "0.0.0.0", "port": 5050, "debug": False, "threaded": True}]


def test_server_skips_requirement_check_with_env_override(monkeypatch, capsys):
    import sys
    from llmflask import __main__ as cli_main

    calls = []

    class FakeApp:
        def run(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("LLMFLASK_SKIP_REQUIREMENTS", "1")
    monkeypatch.setattr("llmflask.app.create_app", lambda **kw: FakeApp())
    monkeypatch.setattr(cli_main, "ollama_reachable", lambda: False)
    monkeypatch.setattr(sys, "argv", ["llmflask", "--server", "--host", "0.0.0.0", "--port", "5050"])

    result = cli_main.main()

    assert result == 0
    assert calls == [{"host": "0.0.0.0", "port": 5050, "debug": False, "threaded": True}]


def test_direct_send_message_uses_system_prompt_without_persisting_it(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.database import create_session, get_messages, init_db
    from llmflask.cli import TuiState, _send_message

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
        def start(self):
            self.target()

    seen = {}

    def fake_chat_stream(messages, model):
        seen["messages"] = list(messages)
        yield "hello"

    monkeypatch.setattr(cli.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(cli, "chat_stream", fake_chat_stream)
    db_path = tmp_path / "direct-chat.db"
    monkeypatch.setattr(cli, "DATABASE", str(db_path))
    init_db(str(db_path))
    sid = create_session(str(db_path), user="alice", title="Direct: DeepSeek", model="deepseek/deepseek-chat")

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek", "Systemprompt")
    state.current_session = sid
    state.current_model = "deepseek/deepseek-chat"
    state.input_text = "hi"

    _send_message(state)

    assert seen["messages"] == [
        {"role": "system", "content": "Systemprompt"},
        {"role": "user", "content": "hi"},
    ]
    assert [(message["role"], message["content"]) for message in state.messages] == [
        ("user", "hi"),
        ("assistant", "hello\n"),
    ]
    assert [(message["role"], message["content"]) for message in get_messages(str(db_path), sid)] == [
        ("user", "hi"),
        ("assistant", "hello\n"),
    ]


def test_direct_send_message_does_not_duplicate_final_newline(monkeypatch, tmp_path):
    from llmflask import cli
    from llmflask.database import create_session, get_messages, init_db
    from llmflask.cli import TuiState, _send_message

    class ImmediateThread:
        def __init__(self, target, daemon=False):
            self.target = target
        def start(self):
            self.target()

    def fake_chat_stream(messages, model):
        yield "hello\n"

    monkeypatch.setattr(cli.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(cli, "chat_stream", fake_chat_stream)
    db_path = tmp_path / "direct-chat.db"
    monkeypatch.setattr(cli, "DATABASE", str(db_path))
    init_db(str(db_path))
    sid = create_session(str(db_path), user="alice", title="Direct: DeepSeek", model="deepseek/deepseek-chat")

    state = TuiState("127.0.0.1", 5000, "alice", "deepseek")
    state.current_session = sid
    state.current_model = "deepseek/deepseek-chat"
    state.input_text = "hi"

    _send_message(state)

    assert [(message["role"], message["content"]) for message in get_messages(str(db_path), sid)] == [
        ("user", "hi"),
        ("assistant", "hello\n"),
    ]
