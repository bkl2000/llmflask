# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest


def _run_main(monkeypatch, argv):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(sys, "argv", argv)
    return cli_main.main()


def test_tui_provider_resolution_prefers_local_server(monkeypatch):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr("llmflask.model_discovery._local_server_available", lambda host, port: True)
    monkeypatch.setattr(
        "llmflask.model_discovery.load_api_keys",
        lambda: pytest.fail("keys must not be loaded when the server is available"),
    )

    assert cli_main._resolve_tui_provider(None, "127.0.0.1", 5000, False) == "server"


@pytest.mark.parametrize(
    "key_name,expected",
    [
        ("DEEPSEEK_API_KEY", "deepseek"),
        ("OPENAI_API_KEY", "openai"),
    ],
)
def test_tui_provider_resolution_falls_back_to_single_key(
    monkeypatch, key_name, expected
):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr("llmflask.model_discovery._local_server_available", lambda host, port: False)
    monkeypatch.setattr("llmflask.model_discovery.load_api_keys", lambda: {key_name: "secret"})

    assert cli_main._resolve_tui_provider(None, "127.0.0.1", 5000, False) == expected


def test_tui_provider_resolution_honors_explicit_choices(monkeypatch):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        "llmflask.model_discovery._local_server_available",
        lambda host, port: pytest.fail("explicit choices must not probe localhost"),
    )

    assert cli_main._resolve_tui_provider("deepseek", "127.0.0.1", 5000, False) == "deepseek"
    assert cli_main._resolve_tui_provider(None, "server", 5000, True) == "server"


@pytest.mark.parametrize(
    "keys,message",
    [
        ({}, "--configure-api-keys"),
        (
            {"DEEPSEEK_API_KEY": "deepseek", "OPENAI_API_KEY": "openai"},
            "Choose --provider",
        ),
    ],
)
def test_tui_provider_resolution_reports_ambiguous_or_missing_keys(
    monkeypatch, keys, message
):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr("llmflask.model_discovery._local_server_available", lambda host, port: False)
    monkeypatch.setattr("llmflask.model_discovery.load_api_keys", lambda: keys)

    with pytest.raises(ValueError, match=message):
        cli_main._resolve_tui_provider(None, "127.0.0.1", 5000, False)


def test_tui_auto_resolution_error_exits_before_curses(monkeypatch, capsys):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr("llmflask.model_discovery._local_server_available", lambda host, port: False)
    monkeypatch.setattr("llmflask.model_discovery.load_api_keys", lambda: {})

    with pytest.raises(SystemExit) as error:
        _run_main(monkeypatch, ["llmflask", "--tui"])

    assert error.value.code == 2
    assert "--configure-api-keys" in capsys.readouterr().err


def test_management_command_conflicts_with_flag_mode(monkeypatch, capsys):
    with pytest.raises(SystemExit) as error:
        _run_main(
            monkeypatch,
            ["llmflask", "--models", "pool", "list"],
        )

    assert error.value.code == 2
    assert "different modes" in capsys.readouterr().err


def test_models_accepts_direct_provider(monkeypatch, capsys):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(
        "llmflask.model_discovery._direct_provider_models",
        lambda provider: [
            {"name": f"{provider}/chat", "provider": provider, "label": "Chat"}
        ],
    )

    assert _run_main(monkeypatch, ["llmflask", "--models", "--provider", "deepseek"]) == 0
    assert "deepseek/chat\tdeepseek\tChat" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv,message",
    [
        (["llmflask", "--server", "--output", "answer.md"], "--output requires --cmd"),
        (["llmflask", "--usepool", "--text", "work"], "requires --model"),
        (
            [
                "llmflask",
                "--cmd",
                "--text",
                "hi",
                "--provider",
                "deepseek",
                "--model",
                "openai/chat",
            ],
            "requires a deepseek/... model reference",
        ),
        (
            ["llmflask", "--models", "--provider", "deepseek", "--host", "server"],
            "cannot be combined",
        ),
        (["llmflask", "--cmd", "--text", "", "--model", "ollama/test"], "non-empty"),
        (["llmflask", "--models", "--port", "70000"], "between 1 and 65535"),
        (
            ["llmflask", "--cmd", "--text", "hi", "--model", "ollama/test", "--session", "0"],
            "expected a positive integer",
        ),
    ],
)
def test_invalid_combinations_fail_cleanly(monkeypatch, capsys, argv, message):
    with pytest.raises(SystemExit) as error:
        _run_main(monkeypatch, argv)

    assert error.value.code == 2
    assert message in capsys.readouterr().err


def test_pool_run_accepts_options_after_subcommand(monkeypatch):
    from llmflask import __main__ as cli_main

    calls = []
    monkeypatch.setattr(
        cli_main,
        "_run_pool_command",
        lambda args, host, port: calls.append(
            (args.name, args.model, args.result_dir, args.no_result, host, port)
        )
        or 0,
    )

    assert _run_main(
        monkeypatch,
        [
            "llmflask",
            "pool",
            "run",
            "demo",
            "--model",
            "ollama/qwen3:8b",
            "--result-dir",
            "/tmp/results",
        ],
    ) == 0
    assert calls == [("demo", "ollama/qwen3:8b", "/tmp/results", False, "127.0.0.1", 5000)]


@pytest.mark.parametrize(
    "argv",
    [
        ["llmflask", "pool", "remove"],
        ["llmflask", "result", "remove"],
        ["llmflask", "session", "remove"],
    ],
)
def test_remove_commands_require_explicit_target(monkeypatch, argv):
    with pytest.raises(SystemExit) as error:
        _run_main(monkeypatch, argv)
    assert error.value.code == 2


def test_reset_passes_selected_user_and_propagates_status(monkeypatch):
    from llmflask import __main__ as cli_main

    calls = []
    monkeypatch.setattr(
        cli_main,
        "_reset",
        lambda host, port, user: calls.append((host, port, user)) or 1,
    )

    assert _run_main(monkeypatch, ["llmflask", "--user", "alice", "reset"]) == 1
    assert calls == [("127.0.0.1", 5000, "alice")]


def test_result_remove_all_preserves_foreign_directories_and_symlinks(monkeypatch, tmp_path):
    from llmflask import __main__ as cli_main

    valid = tmp_path / "pool-240101-000000"
    valid.mkdir()
    (valid / "pool.json").write_text('{"pool_name": "pool"}', encoding="utf-8")
    foreign = tmp_path / "notes"
    foreign.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr("llmflask.result_cli.DEFAULT_RESULT_DIR", str(tmp_path))

    assert cli_main._result_remove("all") == 0
    assert not valid.exists()
    assert foreign.is_dir()
    assert linked.is_symlink()
    assert outside.is_dir()


@pytest.mark.parametrize("name", ["../outside", "/tmp/outside", "a/b"])
def test_result_commands_reject_paths_outside_root(monkeypatch, tmp_path, name):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr("llmflask.result_cli.DEFAULT_RESULT_DIR", str(tmp_path))
    assert cli_main._result_inspect(name) == 1
    assert cli_main._result_run(name) == 1
    assert cli_main._result_remove(name) == 1


class _Response:
    def __init__(self, content=b""):
        self._content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        midpoint = len(self._content) // 2
        return iter((self._content[:midpoint], self._content[midpoint:]))


class _DownloadClient:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, method, url):
        assert method == "GET"
        return _Response(self.content)


def _archive_bytes(*, unsafe=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        if unsafe:
            member = tarfile.TarInfo("pool/link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            archive.addfile(member)
        else:
            data = json.dumps({"pool_name": "pool"}).encode()
            member = tarfile.TarInfo("pool/pool.json")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def test_result_download_is_atomic_and_returns_actual_name(monkeypatch, tmp_path):
    from llmflask import __main__ as cli_main

    content = _archive_bytes()
    monkeypatch.setattr(cli_main.httpx, "Client", lambda **kwargs: _DownloadClient(content))
    result = cli_main._download_result("http://server", "pool", str(tmp_path))

    assert result is not None
    assert result.parent == tmp_path
    assert result.name.startswith("pool-")
    assert (result / "pool.json").is_file()
    assert not list(tmp_path.glob(".download-*"))


def test_result_download_rejects_archive_links_and_cleans_staging(monkeypatch, tmp_path):
    from llmflask import __main__ as cli_main

    content = _archive_bytes(unsafe=True)
    monkeypatch.setattr(cli_main.httpx, "Client", lambda **kwargs: _DownloadClient(content))

    assert cli_main._download_result("http://server", "pool", str(tmp_path)) is None
    assert list(tmp_path.iterdir()) == []


class _EmptyStreamClient:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, *args, **kwargs):
        return self

    def raise_for_status(self):
        return None

    def iter_lines(self):
        return iter(())


def test_pool_stream_without_done_is_failure(monkeypatch, capsys):
    from llmflask import __main__ as cli_main

    monkeypatch.setattr(cli_main.httpx, "Client", lambda **kwargs: _EmptyStreamClient())
    assert cli_main._run_pool_cli(
        None,
        "work",
        "ollama/qwen3:8b",
        "127.0.0.1",
        5000,
        result_dir=None,
    ) == 1
    assert "before a done event" in capsys.readouterr().err


def test_pool_upload_rejects_symbolic_link_before_reading(tmp_path, capsys):
    from llmflask import __main__ as cli_main

    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    linked = tmp_path / "linked.txt"
    linked.symlink_to(outside)

    assert cli_main._run_pool_cli(
        str(linked),
        "work",
        "ollama/qwen3:8b",
        "127.0.0.1",
        5000,
        result_dir=None,
    ) == 1
    assert "Symbolic-link inputs are not allowed" in capsys.readouterr().err


def test_pool_upload_rejects_file_over_client_limit(
    tmp_path, monkeypatch, capsys
):
    from llmflask import pool_cli

    source = tmp_path / "large.bin"
    source.write_bytes(b"four")
    monkeypatch.setattr(pool_cli, "MAX_UPLOAD_FILE_BYTES", 3)
    monkeypatch.setattr(
        pool_cli.httpx,
        "Client",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("HTTP called")),
    )

    assert pool_cli._run_pool_cli(
        str(source), "work", "ollama/qwen3:8b", "127.0.0.1", 5000
    ) == 1
    assert "File exceeds 3 bytes" in capsys.readouterr().err


def test_pool_upload_rejects_directory_over_count_limit(
    tmp_path, monkeypatch, capsys
):
    from llmflask import pool_cli

    source = tmp_path / "input"
    source.mkdir()
    (source / "one.txt").write_text("one", encoding="utf-8")
    (source / "two.txt").write_text("two", encoding="utf-8")
    monkeypatch.setattr(pool_cli, "MAX_UPLOAD_FILES", 1)

    assert pool_cli._run_pool_cli(
        str(source), "work", "ollama/qwen3:8b", "127.0.0.1", 5000
    ) == 1
    assert "more than 1 files" in capsys.readouterr().err


def test_pool_upload_streams_open_file_without_read_bytes(
    tmp_path, monkeypatch, capsys
):
    from llmflask import pool_cli

    source = tmp_path / "data.txt"
    source.write_text("payload", encoding="utf-8")
    captured = {}

    class InspectingClient(_EmptyStreamClient):
        def stream(self, *args, **kwargs):
            upload = kwargs["files"]["file"][1]
            captured["payload"] = upload.read()
            captured["closed_during_request"] = upload.closed
            return self

    monkeypatch.setattr(pool_cli.httpx, "Client", lambda **_kwargs: InspectingClient())
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda _path: (_ for _ in ()).throw(AssertionError("read_bytes called")),
    )

    assert pool_cli._run_pool_cli(
        str(source), "work", "ollama/qwen3:8b", "127.0.0.1", 5000
    ) == 1
    assert captured == {"payload": b"payload", "closed_during_request": False}
    assert "before a done event" in capsys.readouterr().err


def test_run_subcommand_shows_did_you_mean_hint():
    from llmflask.__main__ import _build_parser
    parser = _build_parser()
    args = parser.parse_args(["run"])
    assert args.command == "run"


def test_run_hint_dispatches_correctly(capsys):
    from llmflask.__main__ import _run_hint
    import pytest
    with pytest.raises(SystemExit) as error:
        _run_hint()
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "pool run" in captured.err
    assert "result run" in captured.err
