# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import shutil
import subprocess
from pathlib import Path


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        capture_output=True,
    )


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(path), *args], cwd=path)


def _commit(path: Path, message: str) -> None:
    _git(path, "add", "-A")
    _git(path, "commit", "-m", message)


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def _publication_fixture(tmp_path: Path, project_root: Path) -> Path:
    source = tmp_path / "source"
    (source / "tools").mkdir(parents=True)
    shutil.copy2(project_root / "tools" / "check-publication.sh", source / "tools")
    shutil.copy2(project_root / "LICENSE", source)
    shutil.copy2(project_root / ".gitattributes", source)
    (source / ".gitignore").write_text(
        "api.txt\n.github-config\n*.db\ncomponents/llmflask/build/\n",
        encoding="utf-8",
    )
    (source / "app.py").write_text(
        "# SPDX-License-Identifier: MIT\n"
        "# Copyright (c) 2024-2026 LLMFlask contributors\n"
        "print('safe')\n",
        encoding="utf-8",
    )
    _git(source, "init", "-b", "master")
    _git(source, "config", "user.name", "Test User")
    _git(source, "config", "user.email", "test@example.com")
    _commit(source, "initial fixture")
    return source


def test_publication_checker_accepts_compliant_committed_tree(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)

    result = _run(["tools/check-publication.sh"], cwd=source)

    assert "Committed publication check passed" in result.stdout


def test_publication_checker_rejects_missing_source_header(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    (source / "unsafe.py").write_text("print('missing header')\n", encoding="utf-8")
    _commit(source, "missing header")

    result = _run(["tools/check-publication.sh"], cwd=source, check=False)

    assert result.returncode != 0
    assert "Missing MIT SPDX header: unsafe.py" in result.stderr


def test_publication_checker_checks_staged_tree(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    (source / "staged.py").write_text("print('staged')\n", encoding="utf-8")
    _git(source, "add", "staged.py")

    result = _run(
        ["tools/check-publication.sh", "--staged"], cwd=source, check=False
    )

    assert result.returncode != 0
    assert "Missing MIT SPDX header: staged.py" in result.stderr


def test_publication_checker_rejects_credential_pattern(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    fake_token = "github" + "_pat_" + "A" * 24
    (source / "NOTES.txt").write_text(fake_token, encoding="utf-8")
    _commit(source, "credential fixture")

    result = _run(["tools/check-publication.sh"], cwd=source, check=False)

    assert result.returncode != 0
    assert "Credential-looking content: NOTES.txt" in result.stderr


def test_publication_checker_rejects_personal_home_path(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    personal_home = "/home/" + "alice"
    (source / "NOTES.txt").write_text(
        f"Local path: {personal_home}/models\n", encoding="utf-8"
    )
    _commit(source, "personal path fixture")

    result = _run(["tools/check-publication.sh"], cwd=source, check=False)

    assert result.returncode != 0
    assert f"Personal home path {personal_home}: NOTES.txt" in result.stderr


def test_publication_checker_rejects_private_network_address(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    private_address = "192" + ".168.50.10"
    (source / "NOTES.txt").write_text(
        f"Private endpoint: {private_address}\n", encoding="utf-8"
    )
    _commit(source, "private address fixture")

    result = _run(["tools/check-publication.sh"], cwd=source, check=False)

    assert result.returncode != 0
    assert "Private-looking content: NOTES.txt" in result.stderr


def test_publication_checker_rejects_generated_archive(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    (source / "generated.tar.gz").write_bytes(b"not a real archive")
    _commit(source, "generated archive fixture")

    result = _run(["tools/check-publication.sh"], cwd=source, check=False)

    assert result.returncode != 0
    assert "Forbidden public artifact: generated.tar.gz" in result.stderr


def test_publication_hook_install_is_idempotent(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    command = ["tools/check-publication.sh", "--install-hooks"]

    first = _run(command, cwd=source)
    second = _run(command, cwd=source)
    hook = source / ".git" / "hooks" / "pre-commit"

    assert hook.stat().st_mode & 0o111
    assert "Managed by tools/check-publication.sh" in hook.read_text()
    assert "Installed publication pre-commit hook" in first.stdout
    assert "already installed" in second.stdout


def test_publication_hook_refuses_unmanaged_hook(tmp_path, project_root):
    source = _publication_fixture(tmp_path, project_root)
    hook = source / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    result = _run(
        ["tools/check-publication.sh", "--install-hooks"],
        cwd=source,
        check=False,
    )

    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"


def _publisher_fixture(tmp_path: Path, project_root: Path) -> tuple[Path, dict[str, str]]:
    source = tmp_path / "publisher"
    tools_dir = source / "tools"
    fake_bin = tmp_path / "fake-bin"
    tools_dir.mkdir(parents=True)
    fake_bin.mkdir()
    shutil.copy2(project_root / "tools" / "publish-github.sh", tools_dir)
    _write_executable(
        tools_dir / "check-publication.sh",
        "#!/bin/sh\necho checker-called\n",
    )
    _write_executable(
        tools_dir / "github-push.sh",
        "#!/bin/sh\necho github-push-called \"${1:-publish}\"\n",
    )
    _write_executable(fake_bin / "make", "#!/bin/sh\necho make-called \"$@\"\n")
    _write_executable(
        fake_bin / "ssh",
        "#!/bin/sh\necho \"Hi public-user! You've successfully authenticated, "
        "but GitHub does not provide shell access.\" >&2\nexit 1\n",
    )
    _git(source, "init", "-b", "master")
    _git(source, "config", "user.name", "Test User")
    _git(source, "config", "user.email", "test@example.com")
    _commit(source, "publisher fixture")
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
    }
    return source, environment


def test_publisher_dry_run_has_no_ssh_or_push(tmp_path, project_root):
    source, environment = _publisher_fixture(tmp_path, project_root)

    result = _run(
        ["tools/publish-github.sh", "--dry-run"], cwd=source, env=environment
    )

    assert "make-called" in result.stdout
    assert "github-push-called --check" in result.stdout
    assert "no network changes were made" in result.stdout
    assert "successfully authenticated" not in result.stdout


def test_publisher_dirty_tree_explains_manual_workflow(tmp_path, project_root):
    source, environment = _publisher_fixture(tmp_path, project_root)
    (source / "uncommitted.txt").write_text("local change\n", encoding="utf-8")

    result = _run(
        ["tools/publish-github.sh", "--dry-run"],
        cwd=source,
        env=environment,
        check=False,
    )

    assert result.returncode != 0
    assert "Review git status and git diff" in result.stderr
    assert "stage only intended files" in result.stderr
    assert "push origin/master before publication" in result.stderr


def test_publisher_accepts_github_ssh_status_one(tmp_path, project_root):
    source, environment = _publisher_fixture(tmp_path, project_root)

    result = _run(["tools/publish-github.sh"], cwd=source, env=environment)

    assert "successfully authenticated" in result.stdout
    assert "GitHub status 1 is expected" in result.stdout
    assert "github-push-called --check" in result.stdout
    assert "github-push-called publish" in result.stdout


def test_auth_help_names_only_public_key(tmp_path, project_root):
    source, environment = _publisher_fixture(tmp_path, project_root)
    public_key = Path(environment["HOME"]) / ".ssh" / "id_ed25519.pub"
    public_key.parent.mkdir(parents=True)
    public_key.write_text("ssh-ed25519 AAAA test-key\n", encoding="utf-8")
    fake_keygen = tmp_path / "fake-bin" / "ssh-keygen"
    _write_executable(fake_keygen, "#!/bin/sh\necho '256 SHA256:test public-key'\n")

    result = _run(
        ["tools/publish-github.sh", "--auth-help"],
        cwd=source,
        env=environment,
    )

    assert "https://github.com/settings/ssh/new" in result.stdout
    assert "Do NOT use ssh-copy-id" in result.stdout
    assert str(public_key) in result.stdout
    assert "cat " in result.stdout
    assert "id_ed25519\n" not in result.stdout


def _install_repository(tmp_path: Path) -> Path:
    source = tmp_path / "install-source"
    source.mkdir()
    (source / "README.md").write_text("# Fixture\n", encoding="utf-8")
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "Test User")
    _git(source, "config", "user.email", "test@example.com")
    _commit(source, "initial source")
    remote = tmp_path / "public.git"
    _git(tmp_path, "clone", "--bare", str(source), str(remote))
    return remote


def _installer_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "installer-bin"
    fake_bin.mkdir()
    make_log = tmp_path / "make.log"
    _write_executable(
        fake_bin / "docker",
        "#!/bin/sh\n[ \"$1 $2\" = 'compose version' ]\n",
    )
    _write_executable(
        fake_bin / "make",
        f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> {make_log}\n",
    )
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "install-home"),
    }
    return environment, make_log


def test_public_installer_clones_and_repeats_minimal_install(tmp_path, project_root):
    remote = _install_repository(tmp_path)
    environment, make_log = _installer_environment(tmp_path)
    target = tmp_path / "checkout"
    command = [
        str(project_root / "tools" / "install-public.sh"),
        "--repo",
        str(remote),
        "--directory",
        str(target),
    ]

    _run(command, cwd=tmp_path, env=environment)
    _run(command, cwd=tmp_path, env=environment)
    calls = make_log.read_text(encoding="utf-8")

    assert (target / ".git").is_dir()
    assert calls.splitlines() == [
        f"-C {target} all",
        f"-C {target} all",
    ]


def test_public_installer_full_mode_and_dirty_refusal(tmp_path, project_root):
    remote = _install_repository(tmp_path)
    environment, make_log = _installer_environment(tmp_path)
    target = tmp_path / "checkout"
    base_command = [
        str(project_root / "tools" / "install-public.sh"),
        "--repo",
        str(remote),
        "--directory",
        str(target),
    ]
    _run([*base_command, "--full-ai"], cwd=tmp_path, env=environment)
    (target / "local.txt").write_text("dirty\n", encoding="utf-8")

    result = _run(base_command, cwd=tmp_path, env=environment, check=False)

    calls = make_log.read_text(encoding="utf-8")
    assert f"-C {target} install-server\n" in calls
    assert f"-C {target} install-standalone\n" in calls
    assert f"-C {target} install-tools\n" in calls
    assert "install-ai-minimal" not in calls
    assert result.returncode != 0
    assert "local changes" in result.stderr
