# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .pool_manager import PoolManager
from .sandbox_runner import SandboxRunner
from .script_generator import generate_pool
from .repair import attempt_repair
from .artifact_manager import atomic_write
from ._utils import load_prompt_file


class Workbench:
    def __init__(
        self,
        pool_root: str | None = None,
        sandbox_image: str = "llmflask-sandbox:1",
        sandbox_timeout: int = 60,
        sandbox_memory: str = "2g",
        sandbox_cpus: str = "2",
        sandbox_pids_limit: int = 128,
        repair_attempts: int = 1,
        max_stdout: int = 1_000_000,
        max_stderr: int = 1_000_000,
        max_artifacts: int = 20,
        max_artifact_bytes: int = 100_000_000,
        max_total_artifact_bytes: int = 100_000_000,
    ):
        from ..config import POOL_ROOT

        self.pool_root = pool_root or POOL_ROOT
        self.pool_manager = PoolManager(self.pool_root)
        self.sandbox = SandboxRunner(
            image=sandbox_image,
            timeout=sandbox_timeout,
            memory=sandbox_memory,
            cpus=sandbox_cpus,
            pids_limit=sandbox_pids_limit,
            max_stdout=max_stdout,
            max_stderr=max_stderr,
            max_artifacts=max_artifacts,
            max_artifact_bytes=max_artifact_bytes,
            max_total_artifact_bytes=max_total_artifact_bytes,
        )
        self.repair_attempts = repair_attempts

    def execute(
        self,
        source: str,
        request: str,
        model_ref: str,
        pool_name: str | None = None,
        reuse: bool = False,
    ) -> Iterator[dict]:
        yield {"status": "creating_pool", "message": "Creating pool..."}

        name = self.pool_manager.create(
            source=source,
            pool_name=pool_name,
            reuse=reuse,
        )
        pool_path = self.pool_manager.pool_path(name)

        yield {
            "status": "pool_created",
            "pool_name": name,
            "message": f"Pool {name!r} created.",
        }

        yield {"status": "generating", "message": "Generating script..."}

        prompt_template = load_prompt_file("pool_generate.md")
        result = generate_pool(str(pool_path), request, model_ref, prompt_template)

        yield {
            "status": "generated",
            "message": "Script generated.",
            "files": result,
        }

        yield {"status": "running", "message": "Running sandbox..."}
        yield from self.run_pool(name, model_ref, emit_running=False)

    def run_pool(
        self,
        name: str,
        model_ref: str,
        *,
        emit_running: bool = True,
    ) -> Iterator[dict]:
        pool_path = self.pool_manager.pool_path(name)
        if emit_running:
            yield {"status": "running", "message": "Running sandbox..."}

        start_time = time.time()
        run_result = self.sandbox.run(str(pool_path))
        repair_count = 0

        if not run_result["success"] and run_result.get("recoverable") and self.repair_attempts > 0:
            yield {"status": "repairing", "message": "Error detected, attempting repair..."}
            main_script = self._main_script(pool_path)
            if main_script is not None:
                original = main_script.read_text(encoding="utf-8")
                fixed = attempt_repair(
                    str(pool_path),
                    str(main_script.relative_to(pool_path)),
                    run_result["stderr"],
                    model_ref,
                )
                if fixed is not None:
                    atomic_write(main_script, fixed.rstrip() + "\n")
                    try:
                        repaired_result = self.sandbox.run(str(pool_path))
                    except BaseException:
                        atomic_write(main_script, original)
                        raise
                    repair_count = 1
                    if repaired_result["success"]:
                        run_result = repaired_result
                    else:
                        atomic_write(main_script, original)
                        run_result = repaired_result
                        run_result["stderr"] = (
                            run_result.get("stderr", "")
                            + "\nAutomatic repair failed; original script restored."
                        ).lstrip()

        duration_ms = int((time.time() - start_time) * 1000)
        self._update_pool_meta(
            name, run_result["success"], run_result["exit_code"], duration_ms, repair_count
        )
        yield {
            "status": "done",
            "success": run_result["success"],
            "exit_code": run_result["exit_code"],
            "stdout": run_result.get("stdout", ""),
            "stderr": run_result.get("stderr", ""),
            "duration_ms": duration_ms,
            "repair_count": repair_count,
            "pool_name": name,
        }

    @staticmethod
    def _main_script(pool_path: Path) -> Path | None:
        for relative in ("scripts/main.py", "scripts/main.sh"):
            candidate = pool_path / relative
            if candidate.is_file():
                return candidate
        return None

    def _update_pool_meta(
        self,
        name: str,
        success: bool,
        exit_code: int,
        duration_ms: int,
        repair_count: int,
    ) -> None:
        meta = self.pool_manager.load_meta(name)
        meta["last_run"] = {
            "success": success,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "repair_count": repair_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.pool_manager.save_meta(name, meta)

    def list_pools(self) -> list[dict]:
        return self.pool_manager.list_pools()

    def pool_info(self, name: str) -> dict:
        path = self.pool_manager.validate(name)
        meta = self.pool_manager.load_meta(name)

        files: dict[str, list[str]] = {}
        for sub in ("input", "scripts", "output", "logs"):
            sub_dir = path / sub
            if sub_dir.is_dir():
                files[sub] = [
                    str(p.relative_to(sub_dir))
                    for p in sorted(sub_dir.rglob("*"))
                    if p.is_file()
                ]

        return {
            "name": name,
            "meta": meta,
            "files": files,
        }

    def remove_pool(self, name: str) -> None:
        self.pool_manager.remove(name)

    def pack_pool(
        self, name: str, without_input: bool = False, output: str | None = None
    ) -> str:
        return self.pool_manager.pack(name, output=output, without_input=without_input)
