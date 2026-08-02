# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import stat


def test_load_api_keys_reads_key_file(tmp_path, monkeypatch):
    from llmflask.services.api_keys import load_api_keys

    key_file = tmp_path / "api.txt"
    key_file.write_text(
        """
        # local secrets
        OPENAI_API_KEY=file-openai
        DEEPSEEK_API_KEY='file-deepseek'
        OTHER=value
        broken
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("LLMFLASK_API_KEYS_FILE", str(key_file))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert load_api_keys() == {
        "OPENAI_API_KEY": "file-openai",
        "DEEPSEEK_API_KEY": "file-deepseek",
    }


def test_load_api_keys_env_overrides_file(tmp_path, monkeypatch):
    from llmflask.services.api_keys import load_api_keys

    key_file = tmp_path / "api.txt"
    key_file.write_text("OPENAI_API_KEY=file-openai\n", encoding="utf-8")
    monkeypatch.setenv("LLMFLASK_API_KEYS_FILE", str(key_file))
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert load_api_keys()["OPENAI_API_KEY"] == "env-openai"


def test_load_api_keys_accepts_custom_provider_key_from_file_and_env(
    tmp_path, monkeypatch
):
    from llmflask.services.api_keys import load_api_keys

    key_file = tmp_path / "api.txt"
    key_file.write_text("CUSTOM_API_KEY=file-value\n", encoding="utf-8")
    monkeypatch.setenv("LLMFLASK_API_KEYS_FILE", str(key_file))
    monkeypatch.setenv("CUSTOM_API_KEY", "env-value")

    assert load_api_keys()["CUSTOM_API_KEY"] == "env-value"


def test_default_api_keys_path_uses_home_config(tmp_path, monkeypatch):
    from llmflask.services.api_keys import default_api_keys_path

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    assert default_api_keys_path() == tmp_path / ".config" / "llmflask" / "api.txt"


def test_load_api_keys_prefers_xdg_then_falls_back_to_working_directory(
    tmp_path, monkeypatch
):
    from llmflask.services.api_keys import load_api_keys

    config_home = tmp_path / "config"
    xdg_file = config_home / "llmflask" / "api.txt"
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    (legacy_dir / "api.txt").write_text(
        "OPENAI_API_KEY=legacy\n", encoding="utf-8"
    )
    monkeypatch.chdir(legacy_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.delenv("LLMFLASK_API_KEYS_FILE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert load_api_keys()["OPENAI_API_KEY"] == "legacy"

    xdg_file.parent.mkdir(parents=True)
    xdg_file.write_text("OPENAI_API_KEY=xdg\n", encoding="utf-8")

    assert load_api_keys()["OPENAI_API_KEY"] == "xdg"


def test_explicit_api_keys_file_wins_over_xdg(tmp_path, monkeypatch):
    from llmflask.services.api_keys import load_api_keys

    explicit_file = tmp_path / "explicit.txt"
    explicit_file.write_text("OPENAI_API_KEY=explicit\n", encoding="utf-8")
    xdg_file = tmp_path / "config" / "llmflask" / "api.txt"
    xdg_file.parent.mkdir(parents=True)
    xdg_file.write_text("OPENAI_API_KEY=xdg\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("LLMFLASK_API_KEYS_FILE", str(explicit_file))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert load_api_keys()["OPENAI_API_KEY"] == "explicit"


def test_configure_api_keys_creates_secure_template_and_runs_visual(
    tmp_path, monkeypatch, capsys
):
    from llmflask.services import api_keys

    calls = []
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("LLMFLASK_API_KEYS_FILE", raising=False)
    monkeypatch.setenv("VISUAL", "test-editor --wait")
    monkeypatch.setenv("EDITOR", "ignored-editor")
    monkeypatch.setattr(
        api_keys.subprocess,
        "run",
        lambda command, check: calls.append((command, check))
        or type("Result", (), {"returncode": 0})(),
    )

    assert api_keys.configure_api_keys() == 0

    key_file = tmp_path / "config" / "llmflask" / "api.txt"
    assert key_file.read_text(encoding="utf-8") == api_keys.KEY_FILE_TEMPLATE
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(key_file.parent.stat().st_mode) == 0o700
    assert calls == [(["test-editor", "--wait", str(key_file)], False)]
    assert f"API key file: {key_file}" in capsys.readouterr().out


def test_configure_api_keys_preserves_content_and_repairs_permissions(
    tmp_path, monkeypatch
):
    from llmflask.services import api_keys

    key_file = tmp_path / "config" / "llmflask" / "api.txt"
    key_file.parent.mkdir(parents=True, mode=0o755)
    key_file.write_text("OPENAI_API_KEY=keep-me\n", encoding="utf-8")
    key_file.chmod(0o644)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("LLMFLASK_API_KEYS_FILE", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", "editor")
    monkeypatch.setattr(
        api_keys.subprocess,
        "run",
        lambda command, check: type("Result", (), {"returncode": 0})(),
    )

    assert api_keys.configure_api_keys() == 0
    assert key_file.read_text(encoding="utf-8") == "OPENAI_API_KEY=keep-me\n"
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(key_file.parent.stat().st_mode) == 0o700


def test_configure_api_keys_honors_custom_file_without_chmodding_parent(
    tmp_path, monkeypatch
):
    from llmflask.services import api_keys

    custom_dir = tmp_path / "shared"
    custom_dir.mkdir(mode=0o755)
    key_file = custom_dir / "keys.txt"
    monkeypatch.setenv("LLMFLASK_API_KEYS_FILE", str(key_file))
    monkeypatch.setenv("EDITOR", "editor")
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setattr(
        api_keys.subprocess,
        "run",
        lambda command, check: type("Result", (), {"returncode": 0})(),
    )

    assert api_keys.configure_api_keys() == 0
    assert stat.S_IMODE(custom_dir.stat().st_mode) == 0o755
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_configure_api_keys_rejects_symlink_and_special_file(
    tmp_path, monkeypatch, capsys
):
    from llmflask.services import api_keys

    real_file = tmp_path / "real.txt"
    real_file.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "linked.txt"
    link.symlink_to(real_file)
    monkeypatch.setenv("LLMFLASK_API_KEYS_FILE", str(link))

    assert api_keys.configure_api_keys() == 1
    assert "not a regular file" in capsys.readouterr().err

    fifo = tmp_path / "keys.fifo"
    os.mkfifo(fifo)
    monkeypatch.setenv("LLMFLASK_API_KEYS_FILE", str(fifo))

    assert api_keys.configure_api_keys() == 1
    assert "not a regular file" in capsys.readouterr().err


def test_configure_api_keys_returns_editor_failure(tmp_path, monkeypatch):
    from llmflask.services import api_keys

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("LLMFLASK_API_KEYS_FILE", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(
        api_keys.subprocess,
        "run",
        lambda command, check: type("Result", (), {"returncode": 7})(),
    )

    assert api_keys.configure_api_keys() == 7
