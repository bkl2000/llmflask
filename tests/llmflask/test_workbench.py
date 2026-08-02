# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import pytest
from pathlib import Path


def _raise_fnf(*args, **kwargs):
    raise FileNotFoundError("docker")


class TestSandboxRunner:
    def test_no_docker_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr("subprocess.run", _raise_fnf)

        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")
        (pool / "scripts" / "main.py").write_text("print('x')\n")

        from llmflask.workbench.sandbox_runner import SandboxRunner, SandboxError

        runner = SandboxRunner()
        with pytest.raises(SandboxError, match="is not available"):
            runner.run(str(pool))

    def test_missing_pool(self, monkeypatch):
        from llmflask.workbench.sandbox_runner import SandboxRunner, SandboxError

        runner = SandboxRunner()
        with pytest.raises(SandboxError, match="Pool directory not found"):
            runner.run("/nonexistent/pool")

    def test_missing_run_sh(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        pool.mkdir()
        (pool / "scripts").mkdir()

        from llmflask.workbench.sandbox_runner import SandboxRunner, SandboxError

        runner = SandboxRunner()
        with pytest.raises(SandboxError, match="Pool validation"):
            runner.run(str(pool))

    def test_successful_run(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\necho done\n")
        (pool / "scripts" / "main.py").write_text("print('ok')\n")

        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            import subprocess
            return subprocess.CompletedProcess(cmd, 0, stdout="done\n", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)

        from llmflask.workbench.sandbox_runner import SandboxRunner

        runner = SandboxRunner()
        result = runner.run(str(pool))

        assert result["success"]
        assert result["exit_code"] == 0
        assert calls[0][0] == "docker"
        assert "--network" in calls[0]
        assert "none" in calls[0]
        assert "--cap-drop" in calls[0]
        assert "ALL" in calls[0]
        assert "--read-only" in calls[0]
        assert "--rm" in calls[0]
        assert "/tmp:rw,noexec,nosuid,nodev,size=64m" in calls[0]

    def test_failed_run_recoverable(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\nexit 1\n")
        (pool / "scripts" / "main.py").write_text("print('broken')\n")

        def fake_run(cmd, **kwargs):
            import subprocess
            if cmd[1] == "rm":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="SyntaxError: invalid syntax")

        monkeypatch.setattr("subprocess.run", fake_run)

        from llmflask.workbench.sandbox_runner import SandboxRunner

        runner = SandboxRunner()
        result = runner.run(str(pool))

        assert not result["success"]
        assert result["exit_code"] == 1
        assert result["recoverable"] is True

    def test_failed_run_unrecoverable(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\nexit 1\n")
        (pool / "scripts" / "main.py").write_text("print('x')\n")

        def fake_run(cmd, **kwargs):
            import subprocess
            if cmd[1] == "rm":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="PermissionError: cannot access /etc/shadow"
            )

        monkeypatch.setattr("subprocess.run", fake_run)

        from llmflask.workbench.sandbox_runner import SandboxRunner

        runner = SandboxRunner()
        result = runner.run(str(pool))

        assert not result["success"]
        assert result["recoverable"] is False

    def test_output_is_spooled_and_returned_with_configured_limits(
        self, tmp_path, monkeypatch
    ):
        pool = tmp_path / "pool"
        for directory in ("input", "scripts", "output", "logs"):
            (pool / directory).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        (pool / "scripts" / "main.py").write_text(
            "print('x')\n", encoding="utf-8"
        )

        def fake_run(cmd, **kwargs):
            import subprocess

            if cmd[1] == "rm":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            assert "capture_output" not in kwargs
            kwargs["stdout"].write("stdout-long")
            kwargs["stderr"].write("stderr-long")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("subprocess.run", fake_run)

        from llmflask.workbench.sandbox_runner import SandboxRunner

        result = SandboxRunner(max_stdout=6, max_stderr=6).run(str(pool))

        assert result["stdout"] == "stdout"
        assert result["stderr"] == "stderr"

    @pytest.mark.parametrize(
        ("file_sizes", "runner_options", "message"),
        [
            ([1, 1], {"max_artifacts": 1}, "more than 1 output artifacts"),
            ([4], {"max_artifact_bytes": 3}, "exceeds 3 bytes"),
        ],
    )
    def test_generated_output_limits_are_enforced(
        self, tmp_path, monkeypatch, file_sizes, runner_options, message
    ):
        pool = tmp_path / "pool"
        for directory in ("input", "scripts", "output", "logs"):
            (pool / directory).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        (pool / "scripts" / "main.py").write_text(
            "print('x')\n", encoding="utf-8"
        )

        def fake_run(cmd, **_kwargs):
            import subprocess

            if cmd[1] == "run":
                for index, size in enumerate(file_sizes):
                    (pool / "output" / f"{index}.bin").write_bytes(b"x" * size)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)

        from llmflask.workbench.sandbox_runner import (
            SandboxOutputLimit,
            SandboxRunner,
        )

        with pytest.raises(SandboxOutputLimit, match=message):
            SandboxRunner(**runner_options).run(str(pool))

    def test_timeout(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")
        (pool / "scripts" / "main.py").write_text("print('x')\n")

        def fake_run(cmd, **kwargs):
            import subprocess
            if cmd[1] == "rm":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise subprocess.TimeoutExpired(cmd, 1)

        monkeypatch.setattr("subprocess.run", fake_run)

        from llmflask.workbench.sandbox_runner import SandboxRunner, SandboxTimeout

        runner = SandboxRunner(timeout=1)
        with pytest.raises(SandboxTimeout):
            runner.run(str(pool))

    def test_rejects_symlink_created_by_sandbox(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _x: "/usr/bin/docker")
        pool = tmp_path / "pool"
        for directory in ("input", "scripts", "output", "logs"):
            (pool / directory).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\n")
        (pool / "scripts" / "main.py").write_text("print('x')\n")
        secret = tmp_path / "host-secret.txt"
        secret.write_text("host secret")

        def fake_run(cmd, **kwargs):
            import subprocess
            if cmd[1] == "run":
                (pool / "output" / "secret-link").symlink_to(secret)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)
        from llmflask.workbench.sandbox_runner import (
            SandboxRunner,
            SandboxSecurityViolation,
        )

        with pytest.raises(SandboxSecurityViolation, match="Symbolic links"):
            SandboxRunner().run(str(pool))
        assert secret.read_text() == "host secret"

    def test_cleanup_failure_is_reported(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _x: "/usr/bin/docker")
        pool = tmp_path / "pool"
        for directory in ("input", "scripts", "output", "logs"):
            (pool / directory).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\n")
        (pool / "scripts" / "main.py").write_text("print('x')\n")

        def fake_run(cmd, **kwargs):
            import subprocess
            if cmd[1] == "rm":
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="busy")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)
        from llmflask.workbench.sandbox_runner import SandboxError, SandboxRunner

        with pytest.raises(SandboxError, match="Could not remove"):
            SandboxRunner().run(str(pool))

    def test_interrupt_still_forces_cleanup(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _x: "/usr/bin/docker")
        pool = tmp_path / "pool"
        for directory in ("input", "scripts", "output", "logs"):
            (pool / directory).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\n")
        (pool / "scripts" / "main.py").write_text("print('x')\n")
        calls = []

        def fake_run(cmd, **kwargs):
            import subprocess
            calls.append(cmd)
            if cmd[1] == "rm":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            raise KeyboardInterrupt

        monkeypatch.setattr("subprocess.run", fake_run)
        from llmflask.workbench.sandbox_runner import SandboxRunner

        with pytest.raises(KeyboardInterrupt):
            SandboxRunner().run(str(pool))
        assert any(call[1:3] == ["rm", "-f"] for call in calls)


class TestScriptGenerator:
    def test_inventory(self, tmp_path):
        from llmflask.workbench.script_generator import _inventory

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "data.csv").write_text("a,b,c\n")
        (input_dir / "sub").mkdir()
        (input_dir / "sub" / "notes.txt").write_text("hello")

        result = _inventory(tmp_path)
        assert "data.csv" in result
        assert "sub/notes.txt" in result

    def test_fill_prompt(self):
        from llmflask.workbench.script_generator import _fill_prompt

        template = "Aufgabe: {{request}}\nEingaben:\n{{inventory}}"
        result = _fill_prompt(template, "analysiere", "  file.csv")
        assert "analysiere" in result
        assert "file.csv" in result

    def test_parse_delimiter_sections(self):
        from llmflask.workbench.script_generator import _parse_delimiter_sections

        response = """--- scripts/main.py
print("hello")
--- requirements.txt
numpy==2.0.0
--- setup.sh
#!/bin/bash
echo setup
--- run.sh
#!/bin/bash
echo run
--- README.md
# Pool"""

        sections = _parse_delimiter_sections(response)
        assert sections["scripts/main.py"] == 'print("hello")'
        assert sections["requirements.txt"] == "numpy==2.0.0"
        assert sections["setup.sh"].startswith("#!/bin/bash")
        assert sections["run.sh"].startswith("#!/bin/bash")
        assert sections["README.md"].startswith("# Pool")

    def test_parse_delimiter_rejects_multiline_filenames(self):
        from llmflask.workbench.script_generator import _parse_delimiter_sections

        response = """--- #!/bin/bash
set -euf -o pipefail
echo broken
--- scripts/main.py
print('ok')"""

        sections = _parse_delimiter_sections(response)
        assert "scripts/main.py" in sections
        assert "#!/bin/bash" not in sections

    def test_parse_response_prefers_delimiter_over_markdown(self):
        from llmflask.workbench.script_generator import _parse_response

        response = """--- scripts/main.py
print('from delimiter')

```python scripts/main.py
print('from markdown')
```"""

        sections = _parse_response(response)
        assert "'from delimiter'" in sections["scripts/main.py"]

    def test_parse_response_fallback_to_markdown(self):
        from llmflask.workbench.script_generator import _parse_response

        response = """Here is the script:

```python main.py
print("hello")
```"""

        sections = _parse_response(response)
        assert sections["scripts/main.py"] == 'print("hello")'

    def test_parse_response_fallback_to_empty(self):
        from llmflask.workbench.script_generator import _parse_response

        assert _parse_response("Just text, no sections.") == {}
        assert _parse_response("") == {}

    def test_write_sections_ignores_invalid_filenames(self, tmp_path):
        from llmflask.workbench.script_generator import _write_sections

        pool = tmp_path / "pool"
        pool.mkdir(parents=True)

        sections = {
            "scripts/main.py": 'print("ok")\n',
            "#!/bin/bash\nset -e": "bad content",
        }
        result = _write_sections(pool, sections)
        assert "scripts/main.py" in result
        assert "#!/bin/bash" not in result

    def test_write_sections_rejects_path_traversal(self, tmp_path):
        from llmflask.workbench.script_generator import _write_sections

        pool = tmp_path / "pool"
        pool.mkdir()
        result = _write_sections(
            pool,
            {"scripts/main.py": "print('ok')", "scripts/../../escaped.py": "bad"},
        )

        assert "scripts/main.py" in result
        assert not (tmp_path / "escaped.py").exists()

    def test_generate_writes_files(self, tmp_path, monkeypatch):
        from llmflask.workbench.script_generator import generate_pool

        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)

        fake_response = (
            "--- scripts/main.py (oder main.sh)\n"
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "echo 'done'\n"
            "--- requirements.txt\n"
            "pandas\n"
            "--- setup.sh\n"
            "#!/usr/bin/env bash\n"
            "echo setup\n"
            "--- run.sh\n"
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "bash /pool/scripts/main.sh\n"
            "--- README.md\n"
            "# Test Pool\n"
        )

        def fake_stream(messages, model_ref):
            yield from fake_response

        monkeypatch.setattr(
            "llmflask.workbench.script_generator.chat_stream",
            fake_stream,
        )

        result = generate_pool(
            str(pool),
            "test request",
            "ollama/test-model",
            "Prompt: {{request}}\n{{inventory}}",
        )

        assert "scripts/main.sh" in result
        assert (pool / "scripts" / "main.sh").read_text().startswith("#!/usr/bin/env bash")
        assert (pool / "requirements.txt").read_text() == "pandas\n"
        assert (pool / "setup.sh").exists()
        assert (pool / "run.sh").exists()
        assert (pool / "README.md").exists()

    def test_fallback_sections_when_parse_fails(self, tmp_path, monkeypatch):
        from llmflask.workbench.script_generator import generate_pool, _fallback_sections

        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)

        llm_text = "Hier ist die Analyse der Daten. Die CSV hat 42 Zeilen."

        def fake_stream(messages, model_ref):
            yield from llm_text

        monkeypatch.setattr(
            "llmflask.workbench.script_generator.chat_stream",
            fake_stream,
        )

        result = generate_pool(
            str(pool),
            "zusammenfassen",
            "ollama/test-model",
            "Prompt: {{request}}\n{{inventory}}",
        )

        assert "scripts/main.txt" in result
        assert "setup.sh" in result
        assert "run.sh" in result
        assert "README.md" in result
        assert (pool / "scripts" / "main.txt").read_text().strip() == llm_text.strip()
        assert (pool / "logs" / "llm_response.txt").read_text() == llm_text

    def test_strip_code_fences_removes_markers(self):
        from llmflask.workbench._utils import strip_code_fences

        response = "```python\nprint('hello')\n```"
        cleaned = strip_code_fences(response)
        assert cleaned == "print('hello')"
        assert "```" not in cleaned

    def test_fallback_with_code_fences_strips_them(self, tmp_path, monkeypatch):
        from llmflask.workbench.script_generator import generate_pool

        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)

        llm_text = "```python\nprint('hello from sandbox')\n```"

        def fake_stream(messages, model_ref):
            yield from llm_text

        monkeypatch.setattr(
            "llmflask.workbench.script_generator.chat_stream",
            fake_stream,
        )

        result = generate_pool(
            str(pool),
            "test",
            "ollama/test-model",
            "Prompt: {{request}}\n{{inventory}}",
        )

        assert "scripts/main.py" in result
        content = (pool / "scripts" / "main.py").read_text()
        assert "print('hello from sandbox')" in content
        assert "```" not in content

    def test_write_sections_sets_file_permissions(self, tmp_path):
        from llmflask.workbench.script_generator import _write_sections
        import stat
        import os

        pool = tmp_path / "pool"
        (pool / "scripts").mkdir(parents=True)

        sections = {"scripts/main.py": "print('hello')\n"}
        result = _write_sections(pool, sections)

        assert "scripts/main.py" in result
        mode = os.stat(pool / "scripts" / "main.py").st_mode
        assert stat.S_IMODE(mode) == 0o644

    def test_wrap_with_args_preserves_argparse_code(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = "import argparse\nparser = argparse.ArgumentParser()\n"
        result = _wrap_with_args(code)
        assert result == code

    def test_wrap_with_args_adds_import_sys_for_sys_argv(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = "print(sys.argv[0])\n"
        result = _wrap_with_args(code)
        assert "import sys\n" in result
        assert "print(sys.argv[0])" in result

    def test_wrap_with_args_preserves_sys_argv_with_import_sys(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = "import sys\nprint(sys.argv[:])\n"
        result = _wrap_with_args(code)
        assert result == code

    def test_wrap_with_args_adds_input_output_args_fallback(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = "print('hello')\n"
        result = _wrap_with_args(code)
        assert "INPUT = _arg('--input'" in result
        assert "OUTPUT = _arg('--output'" in result
        assert "import sys, os" in result

    def test_wrap_with_args_replaces_hardcoded_pool_input(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = 'open("/pool/input/data.csv")\n'
        result = _wrap_with_args(code)
        assert "/pool/input" not in result
        assert "INPUT" in result

    def test_wrap_with_args_replaces_hardcoded_pool_output(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = 'save("/pool/output/result.txt")\n'
        result = _wrap_with_args(code)
        assert "/pool/output" not in result
        assert "OUTPUT" in result

    def test_wrap_with_args_replaces_quoted_pool_input(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = 'path = os.path.join("/pool/input", name)\n'
        result = _wrap_with_args(code)
        assert "/pool/input" not in result
        assert '/pool/input' not in result
        assert "INPUT" in result
        assert '"INPUT"' not in result

    def test_wrap_with_args_replaces_both_pool_paths(self):
        from llmflask.workbench.script_generator import _wrap_with_args
        code = 'inp = "/pool/input"\nout = "/pool/output"\n'
        result = _wrap_with_args(code)
        assert "/pool/input" not in result
        assert "/pool/output" not in result


class TestSandboxMountsAndRecovery:
    def test_docker_mounts_include_root_files(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")
        (pool / "setup.sh").write_text("#!/bin/bash\necho setup\n")
        (pool / "requirements.txt").write_text("pandas\n")

        from llmflask.workbench.sandbox_runner import _build_docker_command

        cmd = _build_docker_command(
            "/usr/bin/docker", "test-image", pool,
            timeout=60, memory="2g", cpus="2", pids_limit=128,
        )

        mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
        assert any("/pool/run.sh:ro" in m for m in mounts)
        assert any("/pool/setup.sh:ro" in m for m in mounts)
        assert any("/pool/requirements.txt:ro" in m for m in mounts)
        assert any("/pool/input:ro" in m for m in mounts)
        assert any("/pool/scripts:ro" in m for m in mounts)
        assert any("/pool/output:rw" in m for m in mounts)
        assert any("/pool/logs:rw" in m for m in mounts)

    def test_docker_mounts_skip_missing_root_files(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")

        from llmflask.workbench.sandbox_runner import _build_docker_command

        cmd = _build_docker_command(
            "/usr/bin/docker", "test-image", pool,
            timeout=60, memory="2g", cpus="2", pids_limit=128,
        )

        mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
        assert not any("setup.sh" in m for m in mounts)
        assert not any("requirements.txt" in m for m in mounts)

    def test_is_recoverable_syntax_error(self):
        from llmflask.workbench.sandbox_runner import _is_recoverable

        assert _is_recoverable("SyntaxError: invalid syntax") is True
        assert _is_recoverable("NameError: name 'x' is not defined") is True
        assert _is_recoverable("TypeError: unsupported operand") is True

    def test_is_recoverable_permission_denied(self):
        from llmflask.workbench.sandbox_runner import _is_recoverable

        assert _is_recoverable("Permission denied") is False
        assert _is_recoverable("PermissionError: [Errno 13]") is False
        assert _is_recoverable("Operation not permitted") is False

    def test_is_recoverable_network_and_imports(self):
        from llmflask.workbench.sandbox_runner import _is_recoverable

        assert _is_recoverable("Network is unreachable") is False
        assert _is_recoverable("Could not resolve host") is False
        assert _is_recoverable("Connection refused") is False
        assert _is_recoverable("ModuleNotFoundError: No module named 'foo'") is True
        assert _is_recoverable("ImportError: cannot import") is True
        assert _is_recoverable("No such file or directory") is True

    def test_validate_pool_unreadable_file(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")
        (pool / "run.sh").chmod(0o644)
        main_py = pool / "scripts" / "main.py"
        main_py.write_text("print('hello')\n")
        main_py.chmod(0o600)

        from llmflask.workbench.sandbox_runner import SandboxRunner, SandboxError

        runner = SandboxRunner()
        with pytest.raises(SandboxError, match="Unreadable files"):
            runner.run(str(pool))

    def test_validate_pool_accepts_644(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")
        (pool / "run.sh").chmod(0o644)
        main_py = pool / "scripts" / "main.py"
        main_py.write_text("print('hello')\n")
        main_py.chmod(0o644)

        def fake_run(cmd, **kwargs):
            import subprocess
            return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)

        from llmflask.workbench.sandbox_runner import SandboxRunner

        runner = SandboxRunner()
        result = runner.run(str(pool))
        assert result["success"]

    def test_validate_pool_rejects_unreachable_scripts_dir(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")
        (pool / "run.sh").chmod(0o644)
        (pool / "scripts" / "main.py").write_text("print('hello')\n")
        (pool / "scripts" / "main.py").chmod(0o644)
        (pool / "scripts").chmod(0o700)

        from llmflask.workbench.sandbox_runner import SandboxRunner, SandboxError

        runner = SandboxRunner()
        with pytest.raises(SandboxError, match="Inaccessible directories"):
            runner.run(str(pool))

    def test_write_sections_chmods_directories(self, tmp_path):
        from llmflask.workbench.script_generator import _write_sections
        import stat
        import os

        pool = tmp_path / "pool"
        pool.mkdir(parents=True)
        (pool / "scripts").mkdir()
        (pool / "output").mkdir()

        sections = {"scripts/main.py": "print('hello')\n"}
        _write_sections(pool, sections)

        assert stat.S_IMODE(os.stat(pool / "scripts").st_mode) == 0o755
        assert stat.S_IMODE(os.stat(pool / "output").st_mode) == 0o777
        assert stat.S_IMODE(os.stat(pool / "scripts" / "main.py").st_mode) == 0o644

    def test_ensure_run_sh_python_if_main_py_exists(self, tmp_path):
        from llmflask.workbench.script_generator import _ensure_run_sh

        pool = tmp_path / "pool"
        (pool / "scripts").mkdir(parents=True)
        (pool / "scripts" / "main.py").write_text("print('hello')\n")

        result = _ensure_run_sh(pool)
        assert result == "run.sh"
        content = (pool / "run.sh").read_text()
        assert "scripts/main.py" in content
        assert "scripts/main.sh" not in content

    def test_ensure_run_sh_bash_if_main_sh_exists(self, tmp_path):
        from llmflask.workbench.script_generator import _ensure_run_sh

        pool = tmp_path / "pool"
        (pool / "scripts").mkdir(parents=True)
        (pool / "scripts" / "main.sh").write_text("#!/bin/bash\necho ok\n")

        result = _ensure_run_sh(pool)
        assert result == "run.sh"
        content = (pool / "run.sh").read_text()
        assert "scripts/main.sh" in content
        assert "scripts/main.py" not in content

    def test_ensure_run_sh_none_if_only_txt(self, tmp_path):
        from llmflask.workbench.script_generator import _ensure_run_sh

        pool = tmp_path / "pool"
        (pool / "scripts").mkdir(parents=True)
        (pool / "scripts" / "main.txt").write_text("text\n")

        result = _ensure_run_sh(pool)
        assert result == "run.sh"
        content = (pool / "run.sh").read_text()
        assert "No executable script" in content

    def test_ensure_run_sh_overwrites_existing(self, tmp_path):
        from llmflask.workbench.script_generator import _ensure_run_sh

        pool = tmp_path / "pool"
        (pool / "scripts").mkdir(parents=True)
        (pool / "scripts" / "main.py").write_text("print('ok')\n")
        (pool / "run.sh").write_text("custom run.sh\n")

        _ensure_run_sh(pool)
        content = (pool / "run.sh").read_text()
        assert "scripts/main.py" in content
        assert "custom run.sh" not in content

    def test_parse_markdown_blocks_extracts_code(self):
        from llmflask.workbench.script_generator import _parse_markdown_blocks

        md = """Hier ist das Script:

```python main.py
print("hello")
```

Und hier die dependencies:

```requirements.txt
pandas
```"""

        sections = _parse_markdown_blocks(md)
        assert sections["scripts/main.py"] == 'print("hello")'
        assert sections["requirements.txt"] == "pandas"

    def test_parse_markdown_blocks_bash(self):
        from llmflask.workbench.script_generator import _parse_markdown_blocks

        md = "```bash main.sh\n#!/bin/bash\necho ok\n```"

        sections = _parse_markdown_blocks(md)
        assert sections["scripts/main.sh"] == "#!/bin/bash\necho ok"

    def test_parse_markdown_blocks_empty(self):
        from llmflask.workbench.script_generator import _parse_markdown_blocks

        assert _parse_markdown_blocks("Keine Codebloecke.") == {}
        assert _parse_markdown_blocks("") == {}

    def test_validate_pool_empty_script(self, tmp_path, monkeypatch):
        pool = tmp_path / "pool"
        for d in ("input", "scripts", "output", "logs"):
            (pool / d).mkdir(parents=True)
        (pool / "output").chmod(0o777)
        (pool / "logs").chmod(0o777)
        (pool / "run.sh").write_text("#!/bin/bash\necho ok\n")
        (pool / "scripts" / "main.py").write_text("")

        from llmflask.workbench.sandbox_runner import SandboxRunner, SandboxError

        runner = SandboxRunner()
        with pytest.raises(SandboxError, match="Empty scripts"):
            runner.run(str(pool))
