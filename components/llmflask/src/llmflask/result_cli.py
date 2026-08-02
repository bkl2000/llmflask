# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import RESULT_DIR as DEFAULT_RESULT_DIR, is_safe_name


def _run_result_command(args) -> int:
    handlers = {
        "list":    lambda: _result_list(),
        "inspect": lambda: _result_inspect(args.name),
        "run":     lambda: _result_run(args.name),
        "remove":  lambda: _result_remove(args.name),
    }
    handler = handlers.get(args.result_action)
    if handler:
        return handler()
    print("llmflask: error: Use: result list | inspect | run | remove", file=sys.stderr)
    return 1


def _result_root() -> Path:
    return Path(DEFAULT_RESULT_DIR).expanduser().resolve()


def _safe_result_path(name: str) -> Path:
    if not is_safe_name(name):
        raise ValueError(f"Invalid result name: {name!r}")
    target = _result_root() / name
    if target.is_symlink():
        raise ValueError(f"Symbolic-link results are not allowed: {name!r}")
    return target


def _is_downloaded_result(path: Path) -> bool:
    if path.is_symlink() or not path.is_dir():
        return False
    meta = path / "pool.json"
    if meta.is_symlink() or not meta.is_file():
        return False
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("pool_name"), str)


def _result_list() -> int:
    base = _result_root()
    if not base.is_dir():
        print("No results found.")
        return 0

    results = []
    for entry in sorted(base.iterdir()):
        if _is_downloaded_result(entry):
            try:
                meta = json.loads((entry / "pool.json").read_text())
                last = meta.get("last_run", {}) or {}
                status = "OK" if last.get("success") else ("FAIL" if last else "---")
            except Exception:
                status = "???"
            results.append(f"{entry.name:<50} {status}")

    if not results:
        print("No results found in " + str(base))
        return 0

    print(f"Results in {base}:")
    for r in results:
        print(f"  {r}")
    return 0


def _result_inspect(name: str) -> int:
    try:
        base = _safe_result_path(name)
    except ValueError as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1
    if not _is_downloaded_result(base):
        print(f"llmflask: error: Result not found: {name}", file=sys.stderr)
        return 1

    print(f"Result: {base}")

    for sub in ("input", "scripts", "output", "logs"):
        d = base / sub
        if d.is_dir():
            files = sorted(d.rglob("*"))
            if files:
                print(f"\n{sub}/ ({len(files)} files):")
                for f in files[:20]:
                    print(f"  {f.relative_to(d)}")

    pool_json = base / "pool.json"
    if pool_json.is_file():
        try:
            meta = json.loads(pool_json.read_text())
            last = meta.get("last_run", {}) or {}
            if last:
                print(f"\nLast run: {'OK' if last.get('success') else 'FAILED'} | exit={last.get('exit_code','?')} | {last.get('duration_ms',0)}ms")
            if last.get("stdout"):
                print(f"\n--- stdout ---\n{last['stdout']}")
            if last.get("stderr"):
                print(f"\n--- stderr ---\n{last['stderr']}")
        except Exception:
            pass

    print(f"\nRun locally: cd {base} && bash run.sh")
    return 0


def _result_run(name: str) -> int:
    try:
        base = _safe_result_path(name)
    except ValueError as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1
    if not _is_downloaded_result(base):
        print(f"llmflask: error: Result not found: {name}", file=sys.stderr)
        return 1

    setup_sh = base / "setup.sh"
    if setup_sh.is_file() and not setup_sh.is_symlink():
        try:
            os.chmod(setup_sh, 0o755)
        except FileNotFoundError:
            print(f"llmflask: error: setup.sh disappeared for {name}", file=sys.stderr)
            return 1
        print(f"Running setup.sh for {name}...")
        setup_result = subprocess.run(["bash", str(setup_sh)], cwd=str(base))
        if setup_result.returncode != 0:
            print(f"llmflask: error: setup.sh failed (exit {setup_result.returncode})", file=sys.stderr)
            return setup_result.returncode

    run_sh = base / "run.sh"
    if run_sh.is_symlink() or base not in run_sh.resolve().parents:
        print(f"llmflask: error: No run.sh in {base}", file=sys.stderr)
        return 1
    try:
        os.chmod(run_sh, 0o755)
        result = subprocess.run(["bash", str(run_sh)], cwd=str(base))
    except FileNotFoundError:
        print(f"llmflask: error: run.sh not found in {base}", file=sys.stderr)
        return 1
    return result.returncode


def _result_remove(name: str) -> int:
    base = _result_root()
    if not base.is_dir():
        return 0
    if name == "all":
        count = 0
        for entry in list(base.iterdir()):
            if _is_downloaded_result(entry):
                shutil.rmtree(entry)
                count += 1
        print(f"Deleted {count} result{'s' if count != 1 else ''}.")
        return 0
    try:
        target = _safe_result_path(name)
    except ValueError as error:
        print(f"llmflask: error: {error}", file=sys.stderr)
        return 1
    if not _is_downloaded_result(target):
        print(f"llmflask: error: Result not found: {name}", file=sys.stderr)
        return 1
    shutil.rmtree(target)
    print(f"Deleted result: {name}")
    return 0
