# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import importlib
from pathlib import Path


def _reload_config(monkeypatch):
    import llmflask.config as config

    return importlib.reload(config)


def test_default_database_path_uses_home(monkeypatch, tmp_path):
    monkeypatch.delenv("LLMFLASK_DB", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    config = _reload_config(monkeypatch)

    assert config.DATABASE == str(tmp_path / ".local" / "share" / "llmflask" / "chat.db")


def test_default_database_path_uses_xdg_data_home(monkeypatch, tmp_path):
    data_home = tmp_path / "xdg-data"
    monkeypatch.delenv("LLMFLASK_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    config = _reload_config(monkeypatch)

    assert config.DATABASE == str(data_home / "llmflask" / "chat.db")


def test_database_env_override(monkeypatch, tmp_path):
    db_path = tmp_path / "custom.db"
    monkeypatch.setenv("LLMFLASK_DB", str(db_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    config = _reload_config(monkeypatch)

    assert config.DATABASE == str(db_path)


def test_workbench_limit_and_archive_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("LLMFLASK_POOL_ARCHIVE_ROOT", raising=False)
    monkeypatch.delenv("LLMFLASK_MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.delenv("LLMFLASK_MAX_UPLOAD_FILE_BYTES", raising=False)
    monkeypatch.delenv("LLMFLASK_MAX_UPLOAD_FILES", raising=False)

    config = _reload_config(monkeypatch)

    assert config.POOL_ARCHIVE_ROOT == str(
        tmp_path / ".local" / "share" / "llmflask" / "archives"
    )
    assert config.MAX_UPLOAD_BYTES == 512 * 1024 * 1024
    assert config.MAX_UPLOAD_FILE_BYTES == 256 * 1024 * 1024
    assert config.MAX_UPLOAD_FILES == 1000


def test_legacy_database_is_copied_to_default_path(monkeypatch, tmp_path):
    data_home = tmp_path / "xdg-data"
    workdir = tmp_path / "work"
    workdir.mkdir()
    legacy = workdir / "chat.db"
    legacy.write_bytes(b"legacy-db")
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("LLMFLASK_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    destination = data_home / "llmflask" / "chat.db"
    config = _reload_config(monkeypatch)
    config.prepare_database_path(config.DATABASE)

    assert config.DATABASE == str(destination)
    assert destination.read_bytes() == b"legacy-db"
    assert legacy.exists()


def test_legacy_database_does_not_overwrite_existing_destination(monkeypatch, tmp_path):
    data_home = tmp_path / "xdg-data"
    destination = data_home / "llmflask" / "chat.db"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing-db")
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "chat.db").write_bytes(b"legacy-db")
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("LLMFLASK_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    config = _reload_config(monkeypatch)
    assert config.DATABASE == str(destination)
    config.prepare_database_path(config.DATABASE)

    assert destination.read_bytes() == b"existing-db"


def test_legacy_database_is_ignored_when_db_env_is_set(monkeypatch, tmp_path):
    custom_db = tmp_path / "custom.db"
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "chat.db").write_bytes(b"legacy-db")
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("LLMFLASK_DB", str(custom_db))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    config = _reload_config(monkeypatch)
    config.prepare_database_path(config.DATABASE)

    assert config.DATABASE == str(custom_db)
    assert custom_db.parent.exists()
    assert not custom_db.exists()
