# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import shutil
import subprocess
from pathlib import Path


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        text=True,
        capture_output=True,
    )


def _commit(path: Path, message: str) -> None:
    _git(path, "add", "-A")
    _git(path, "commit", "-m", message)


def _make_source(tmp_path: Path, project_root: Path) -> Path:
    source = tmp_path / "source"
    (source / "tools").mkdir(parents=True)
    (source / "archive" / "legacy-docs").mkdir(parents=True)
    shutil.copy2(project_root / "tools" / "github-push.sh", source / "tools")
    shutil.copy2(
        project_root / "tools" / "check-publication.sh", source / "tools"
    )
    shutil.copy2(project_root / "LICENSE", source)
    shutil.copy2(project_root / ".gitattributes", source)
    (source / ".gitignore").write_text(
        "api.txt\n.github-config\n*.db\ncomponents/llmflask/build/\n",
        encoding="utf-8",
    )
    (source / "README.md").write_text("# Public project\n", encoding="utf-8")
    (source / "archive" / "legacy-docs" / "private.md").write_text(
        "Private Author <private.person@example.com>\n", encoding="utf-8"
    )
    for private_file in (
        "AGENTS.md",
        "OPENCODE_INSTALLATION_PLAN.md",
        "OPENCODE_REVIEW_PLAN.md",
        "PROJECT_TRACE.md",
        "PYTHON_GROSSREFAKTOR_REVIEW.md",
        "llmflask_local_ai_workbench_pool_phase1_AI_Draft_Unreviewed_2026-07-12.md",
        "opencode.json",
        "prompts/ollama_prompt_pack_pythonic.tar.gz",
    ):
        path = source / private_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private-only fixture\n", encoding="utf-8")
    _git(source, "init", "-b", "master")
    _git(source, "config", "user.name", "Private Author")
    _git(source, "config", "user.email", "private.person@example.com")
    _commit(source, "private initial commit")
    return source


def _publisher_env(remote: Path) -> dict[str, str]:
    return {
        **os.environ,
        "GITHUB_USER": "public-user",
        "GITHUB_REPO": "public-repo",
        "GITHUB_REMOTE_URL": str(remote),
    }


def _run_publisher(
    source: Path,
    remote: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(source / "tools" / "github-push.sh"), *args],
        cwd=source,
        env=_publisher_env(remote),
        check=check,
        text=True,
        capture_output=True,
    )


def test_public_snapshot_check_excludes_private_archive(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "unused.git"

    result = _run_publisher(source, remote, "--check")

    assert "Public snapshot check passed" in result.stdout


def test_public_snapshot_check_rejects_private_looking_content(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "unused.git"
    private_email = "private.person@" + "gmail.com"
    (source / "PRIVATE.md").write_text(private_email, encoding="utf-8")
    _commit(source, "add private-looking content")

    result = _run_publisher(source, remote, "--check", check=False)

    assert result.returncode != 0
    assert "Private-looking content" in result.stderr


def test_public_snapshot_check_rejects_personal_home_path(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "unused.git"
    personal_home = "/home/" + "alice"
    (source / "NOTES.md").write_text(
        f"Local path: {personal_home}/models\n", encoding="utf-8"
    )
    _commit(source, "add personal home path")

    result = _run_publisher(source, remote, "--check", check=False)

    assert result.returncode != 0
    assert f"Personal home path {personal_home}: NOTES.md" in result.stderr


def test_public_snapshot_check_rejects_private_network_address(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "unused.git"
    private_address = "172" + ".20.30.40"
    (source / "NOTES.md").write_text(
        f"Private endpoint: {private_address}\n", encoding="utf-8"
    )
    _commit(source, "add private network address")

    result = _run_publisher(source, remote, "--check", check=False)

    assert result.returncode != 0
    assert "Private-looking content: NOTES.md" in result.stderr


def test_public_snapshot_check_rejects_credential_pattern(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "unused.git"
    fake_token = "github" + "_pat_" + "A" * 24
    (source / "NOTES.txt").write_text(fake_token, encoding="utf-8")
    _commit(source, "add credential fixture")

    result = _run_publisher(source, remote, "--check", check=False)

    assert result.returncode != 0
    assert "Credential-looking content: NOTES.txt" in result.stderr


def test_public_snapshot_check_rejects_private_key_material(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "unused.git"
    private_key_marker = "-----BEGIN OPENSSH " + "PRIVATE KEY-----\n"
    (source / "NOTES.txt").write_text(
        private_key_marker + "fake fixture only\n",
        encoding="utf-8",
    )
    _commit(source, "add private key fixture")

    result = _run_publisher(source, remote, "--check", check=False)

    assert result.returncode != 0
    assert "Private-looking content: NOTES.txt" in result.stderr


def test_public_snapshot_check_rejects_generated_archive(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "unused.git"
    (source / "generated.tar.gz").write_bytes(b"not a real archive")
    _commit(source, "add generated archive")

    result = _run_publisher(source, remote, "--check", check=False)

    assert result.returncode != 0
    assert "Forbidden public artifact: generated.tar.gz" in result.stderr


def test_publication_creates_and_updates_separate_history(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "public.git"
    _git(tmp_path, "init", "--bare", str(remote))

    _run_publisher(source, remote)
    checkout = tmp_path / "checkout"
    subprocess.run(
        ["git", "clone", "--quiet", "--branch", "main", str(remote), str(checkout)],
        check=True,
    )
    assert (checkout / ".llmflask-public-snapshot").is_file()
    assert not (checkout / "archive" / "legacy-docs").exists()
    for private_path in (
        "AGENTS.md",
        "OPENCODE_INSTALLATION_PLAN.md",
        "OPENCODE_REVIEW_PLAN.md",
        "PROJECT_TRACE.md",
        "PYTHON_GROSSREFAKTOR_REVIEW.md",
        "llmflask_local_ai_workbench_pool_phase1_AI_Draft_Unreviewed_2026-07-12.md",
        "opencode.json",
        "prompts/ollama_prompt_pack_pythonic.tar.gz",
    ):
        assert not (checkout / private_path).exists()
    assert _git(checkout, "log", "-1", "--format=%ae").stdout.strip() == (
        "public-user@users.noreply.github.com"
    )
    assert _git(checkout, "rev-list", "--count", "HEAD").stdout.strip() == "1"

    (source / "README.md").write_text("# Updated public project\n", encoding="utf-8")
    _commit(source, "private update")
    _run_publisher(source, remote)
    shutil.rmtree(checkout)
    subprocess.run(
        ["git", "clone", "--quiet", "--branch", "main", str(remote), str(checkout)],
        check=True,
    )
    assert _git(checkout, "rev-list", "--count", "HEAD").stdout.strip() == "2"
    assert "Updated public project" in (checkout / "README.md").read_text()


def test_publication_skips_unchanged_snapshot(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    remote = tmp_path / "public.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _run_publisher(source, remote)

    result = _run_publisher(source, remote)

    assert "already current" in result.stdout
    assert _git(remote, "rev-list", "--count", "main").stdout.strip() == "1"


def test_publication_refuses_unmanaged_main(tmp_path, project_root):
    source = _make_source(tmp_path, project_root)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    _git(foreign, "init", "-b", "main")
    _git(foreign, "config", "user.name", "Someone Else")
    _git(foreign, "config", "user.email", "someone@example.com")
    (foreign / "README.md").write_text("# Existing repository\n", encoding="utf-8")
    _commit(foreign, "foreign initial commit")
    remote = tmp_path / "foreign.git"
    _git(tmp_path, "clone", "--bare", str(foreign), str(remote))

    result = _run_publisher(source, remote, check=False)

    assert result.returncode != 0
    assert "was not created by this publisher" in result.stderr
