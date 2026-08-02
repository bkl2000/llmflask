# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import IO
from typing import Optional, TypedDict

from .pool_manager import UnsafePoolError, validate_regular_tree


class SandboxResult(TypedDict):
    success: bool
    exit_code: int
    stdout: str
    stderr: str


class SandboxResultRecoverable(SandboxResult, total=False):
    recoverable: bool


class SandboxError(Exception):
    """Error during sandbox execution."""


class SandboxTimeout(SandboxError):
    """Timeout during sandbox execution."""


class SandboxSecurityViolation(SandboxError):
    """Security violation in sandbox."""


class SandboxOutputLimit(SandboxError):
    """Generated output exceeds the configured artifact limits."""


def _bounded_process_output(
    captured: str | None,
    sink: IO[str],
    limit: int,
) -> str:
    if captured is not None:
        return captured[:limit]
    sink.flush()
    sink.seek(0)
    return sink.read(limit)


def _build_docker_command(
    runtime: str,
    image: str,
    pool_path: Path,
    timeout: int,
    memory: str,
    cpus: str,
    pids_limit: int,
) -> list[str]:
    input_path = pool_path / "input"
    scripts_path = pool_path / "scripts"
    output_path = pool_path / "output"
    logs_path = pool_path / "logs"

    cmd = [
        runtime, "run",
        "--rm",
        "--network", "none",
        "--memory", memory,
        "--cpus", cpus,
        "--pids-limit", str(pids_limit),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--user", "10001:10001",
        "-v", f"{input_path}:/pool/input:ro",
        "-v", f"{scripts_path}:/pool/scripts:ro",
        "-v", f"{output_path}:/pool/output:rw",
        "-v", f"{logs_path}:/pool/logs:rw",
    ]

    for name in ("run.sh", "setup.sh", "requirements.txt", "apt-packages.txt", "README.md", "pool.json"):
        f = pool_path / name
        if f.is_file():
            cmd.extend(["-v", f"{f}:/pool/{name}:ro"])

    cmd.extend([image, "bash", "/pool/run.sh"])
    return cmd


class SandboxRunner:
    def __init__(
        self,
        image: str = "llmflask-sandbox:1",
        timeout: int = 60,
        memory: str = "2g",
        cpus: str = "2",
        pids_limit: int = 128,
        max_stdout: int = 1_000_000,
        max_stderr: int = 1_000_000,
        max_artifacts: int = 20,
        max_artifact_bytes: int = 100_000_000,
        max_total_artifact_bytes: int = 100_000_000,
    ):
        self.image = image
        self.timeout = timeout
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit
        self.max_stdout = max_stdout
        self.max_stderr = max_stderr
        self.max_artifacts = max_artifacts
        self.max_artifact_bytes = max_artifact_bytes
        self.max_total_artifact_bytes = max_total_artifact_bytes
        from ..config import SANDBOX_RUNTIME
        self._runtime = SANDBOX_RUNTIME

    def _validate_pool(self, pool_dir: Path) -> None:
        try:
            validate_regular_tree(pool_dir)
        except UnsafePoolError as exc:
            raise SandboxSecurityViolation(str(exc)) from exc
        missing: list[str] = []
        unreadable: list[str] = []
        unreachable_dir: list[str] = []
        empty_script: list[str] = []

        for path in ("run.sh", "scripts/main.py", "scripts/main.sh"):
            f = pool_dir / path
            if f.is_file():
                if not (f.stat().st_mode & stat.S_IROTH):
                    unreadable.append(f"{path} ({oct(f.stat().st_mode)})")
                elif f.stat().st_size == 0:
                    empty_script.append(path)
            elif path == "run.sh":
                missing.append(path)

        has_main = (pool_dir / "scripts/main.py").is_file() or (pool_dir / "scripts/main.sh").is_file()

        scripts_dir = pool_dir / "scripts"
        if scripts_dir.is_dir() and not (scripts_dir.stat().st_mode & stat.S_IXOTH):
            unreachable_dir.append(f"scripts/ ({oct(scripts_dir.stat().st_mode)})")

        for sub in ("output", "logs"):
            d = pool_dir / sub
            if d.is_dir() and not (d.stat().st_mode & stat.S_IWOTH):
                unreachable_dir.append(f"{sub}/ not writable ({oct(d.stat().st_mode)})")

        errors: list[str] = []
        if missing:
            errors.append(f"Missing files: {', '.join(missing)}")
        if not has_main:
            errors.append("No script found: neither scripts/main.py nor scripts/main.sh")
        if unreadable:
            errors.append(f"Unreadable files: {', '.join(unreadable)}")
        if unreachable_dir:
            errors.append(f"Inaccessible directories: {', '.join(unreachable_dir)}")
        if empty_script:
            errors.append(f"Empty scripts: {', '.join(empty_script)}")

        if errors:
            raise SandboxError("Pool validation failed:\n" + "\n".join(errors))

    def _validate_output_artifacts(self, pool_dir: Path) -> None:
        output_dir = pool_dir / "output"
        artifacts = [path for path in output_dir.rglob("*") if path.is_file()]
        if len(artifacts) > self.max_artifacts:
            raise SandboxOutputLimit(
                f"Sandbox created more than {self.max_artifacts} output artifacts"
            )
        oversized = next(
            (
                path
                for path in artifacts
                if path.stat().st_size > self.max_artifact_bytes
            ),
            None,
        )
        if oversized is not None:
            relative = oversized.relative_to(output_dir)
            raise SandboxOutputLimit(
                f"Sandbox output artifact exceeds {self.max_artifact_bytes} bytes: "
                f"{relative}"
            )
        total_bytes = sum(p.stat().st_size for p in artifacts)
        if total_bytes > self.max_total_artifact_bytes:
            raise SandboxOutputLimit(
                f"Sandbox total output ({total_bytes / 1_000_000:.1f} MiB) exceeds "
                f"limit ({self.max_total_artifact_bytes / 1_000_000:.1f} MiB)"
            )

    def run(self, pool_path: str) -> SandboxResult:
        pool_dir = Path(pool_path).expanduser().absolute()
        if not pool_dir.is_dir():
            raise SandboxError(f"Pool directory not found: {pool_path}")

        self._validate_pool(pool_dir)

        cid = f"llmflask-pool-{os.urandom(4).hex()}"

        cmd = _build_docker_command(
            self._runtime,
            self.image,
            pool_dir,
            self.timeout,
            self.memory,
            self.cpus,
            self.pids_limit,
        )
        cmd.insert(2, "--name")
        cmd.insert(3, cid)

        with (
            tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_sink,
            tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_sink,
        ):
            try:
                result = subprocess.run(
                    cmd,
                    stdout=stdout_sink,
                    stderr=stderr_sink,
                    text=True,
                    timeout=self.timeout,
                )
            except FileNotFoundError:
                from ..config import SANDBOX_RUNTIME
                raise SandboxError(
                    f"{SANDBOX_RUNTIME} is not available. "
                    "Install Docker Engine and try again."
                ) from None
            except BaseException as exc:
                try:
                    self._remove_container(cid, force=True)
                except SandboxError as cleanup_error:
                    exc.add_note(str(cleanup_error))
                if isinstance(exc, subprocess.TimeoutExpired):
                    raise SandboxTimeout(
                        f"Sandbox execution timed out after {self.timeout}s"
                    ) from exc
                raise
            else:
                self._remove_container(cid, force=True)

            stdout = _bounded_process_output(
                result.stdout, stdout_sink, self.max_stdout
            )
            stderr = _bounded_process_output(
                result.stderr, stderr_sink, self.max_stderr
            )

        try:
            validate_regular_tree(pool_dir)
        except UnsafePoolError as exc:
            raise SandboxSecurityViolation(str(exc)) from exc
        self._validate_output_artifacts(pool_dir)

        if result.returncode != 0:
            return {
                "success": False,
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "recoverable": _is_recoverable(stderr),
            }

        return {
            "success": True,
            "exit_code": 0,
            "stdout": stdout,
            "stderr": stderr,
        }

    def _remove_container(self, cid: str, force: bool = False) -> None:
        args = [self._runtime, "rm"]
        if force:
            args.append("-f")
        args.append(cid)
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired as exc:
            raise SandboxError(f"Timed out while removing sandbox container {cid}") from exc
        if result.returncode != 0 and "No such container" not in result.stderr:
            raise SandboxError(
                f"Could not remove sandbox container {cid}: {result.stderr.strip()}"
            )


def _is_recoverable(stderr: str) -> bool:
    unrecoverable_markers = [
        "Permission denied",
        "PermissionError",
        "Operation not permitted",
        "Network is unreachable",
        "Could not resolve host",
        "Connection refused",
        "cannot access",
    ]
    for marker in unrecoverable_markers:
        if marker in stderr:
            return False
    return True
