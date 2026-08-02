# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
from pathlib import Path


class TestArtifactManager:
    def test_atomic_write(self, tmp_path):
        from llmflask.workbench.artifact_manager import atomic_write

        target = tmp_path / "sub" / "file.txt"
        atomic_write(target, "content\n")

        assert target.read_text() == "content\n"

    def test_atomic_write_overwrite(self, tmp_path):
        from llmflask.workbench.artifact_manager import atomic_write

        target = tmp_path / "file.txt"
        target.write_text("old")
        atomic_write(target, "new\n")

        assert target.read_text() == "new\n"

    def test_backup_and_restore(self, tmp_path):
        from llmflask.workbench.artifact_manager import (
            backup_existing,
            restore_backup,
            discard_backup,
        )

        target = tmp_path / "file.txt"
        target.write_text("old\n")

        backup = backup_existing(target)
        assert backup is not None
        assert not target.exists()
        assert backup.exists()
        assert str(backup) == str(tmp_path / "file.txt.backup")

        restore_backup(backup, target)
        assert target.read_text() == "old\n"
        assert not backup.exists()

    def test_backup_nonexistent(self, tmp_path):
        from llmflask.workbench.artifact_manager import backup_existing

        backup = backup_existing(tmp_path / "nope.txt")
        assert backup is None

    def test_workflow_no_destroy_on_failure(self, tmp_path):
        from llmflask.workbench.artifact_manager import (
            atomic_write,
            backup_existing,
            restore_backup,
        )

        target = tmp_path / "output" / "result.json"
        target.parent.mkdir()
        atomic_write(target, json.dumps({"version": 1}))

        backup = backup_existing(target)
        atomic_write(tmp_path / "output" / ".tmp", "invalid")

        restore_backup(backup, target)
        assert target.read_text() == '{"version": 1}'


class TestRepair:
    def test_repair_returns_fixed_script(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        pool.mkdir()
        (pool / "scripts").mkdir(parents=True)
        (pool / "scripts" / "main.py").write_text("print('broken'")

        fixed_response = "print('fixed')\n"

        def fake_stream(messages, model_ref):
            yield from fixed_response

        monkeypatch.setattr(
            "llmflask.workbench.repair.chat_stream",
            fake_stream,
        )

        monkeypatch.setattr(
            "llmflask.workbench.repair.load_prompt_file",
            lambda name: "Error: {{error_output}}\nScript: {{script_path}}\nContent:\n{{script_content}}",
        )

        from llmflask.workbench.repair import attempt_repair

        result = attempt_repair(
            str(pool),
            "scripts/main.py",
            "SyntaxError: invalid syntax",
            "ollama/test-model",
        )

        assert result == "print('fixed')"

    def test_repair_no_change_returns_none(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        pool.mkdir()
        (pool / "scripts").mkdir(parents=True)
        original = "print('hello')\n"
        (pool / "scripts" / "main.py").write_text(original)

        def fake_stream(messages, model_ref):
            yield from original

        monkeypatch.setattr(
            "llmflask.workbench.repair.chat_stream",
            fake_stream,
        )

        monkeypatch.setattr(
            "llmflask.workbench.repair.load_prompt_file",
            lambda name: "{{error_output}}\n{{script_path}}\n{{script_content}}",
        )

        from llmflask.workbench.repair import attempt_repair

        result = attempt_repair(
            str(pool),
            "scripts/main.py",
            "some error",
            "ollama/test-model",
        )

        assert result is None

    def test_repair_missing_script(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        pool.mkdir()

        monkeypatch.setattr(
            "llmflask.workbench.repair.load_prompt_file",
            lambda name: "prompt",
        )

        from llmflask.workbench.repair import attempt_repair

        result = attempt_repair(
            str(pool),
            "scripts/missing.py",
            "error",
            "ollama/test-model",
        )

        assert result is None
