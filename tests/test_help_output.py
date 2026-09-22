# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import subprocess
import sys
from pathlib import Path


def test_all_tracked_executable_shell_scripts_support_help(project_root):
    result = subprocess.run(
        ["git", "ls-files", "*.sh"],
        cwd=project_root,
        check=True,
        text=True,
        capture_output=True,
    )

    scripts = [
        line
        for line in result.stdout.splitlines()
        if line
        and (project_root / line).is_file()
        and (project_root / line).stat().st_mode & 0o111
    ]
    assert scripts

    for script in scripts:
        completed = subprocess.run(
            ["bash", script, "--help"],
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=5,
        )
        assert completed.returncode == 0, script
        assert "Usage:" in completed.stdout, script


def test_llmflask_help_lists_common_modes(capsys, monkeypatch):
    import pytest

    package_src = Path(__file__).resolve().parent.parent / "components" / "llmflask" / "src"
    sys.path.insert(0, str(package_src))
    from llmflask.__main__ import main

    monkeypatch.setattr(sys, "argv", ["llmflask", "--help"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--usepool" in output
    assert "--cmd" in output
    assert "--model" in output
    assert "--models" in output
    assert "--tui" in output
    assert "Pool Workbench" in output
    assert "Quick Start" in output
