# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import os
import shutil
import hashlib
import re
import subprocess
import tempfile
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .artifact_manager import atomic_write

from ..config import is_safe_name


class UnsafePoolError(ValueError):
    """A pool contains a link or special file that must not be dereferenced."""


def _validate_pool_name(name: str) -> str:
    if not is_safe_name(name):
        raise ValueError(f"Invalid pool name: {name!r}")
    return name


def _sanitize_basename(path: str) -> str:
    base = Path(path).name
    if base in (".", ".."):
        return "pool"
    return base


def _make_pool_name(source: str) -> str:
    base = _sanitize_basename(source)
    return f"{base}-pool"


def _resolve_name(pool_root: Path, preferred: Optional[str], source: str) -> str:
    if preferred:
        return _validate_pool_name(preferred)
    name = _make_pool_name(source)
    if not is_safe_name(name):
        name = "pool"
    return _unique_name(pool_root, name)


def _unique_name(pool_root: Path, base_name: str) -> str:
    if not (pool_root / base_name).exists():
        return base_name
    stem = base_name
    counter = 2
    while (pool_root / f"{stem}-{counter}").exists():
        counter += 1
    return f"{stem}-{counter}"


def _compute_hash(source_path: Path) -> str:
    hasher = hashlib.sha256()
    paths: list[Path]
    if source_path.is_dir():
        paths = sorted(p for p in source_path.rglob("*") if p.is_file())
    else:
        paths = [source_path]
    for path in paths:
        with path.open("rb") as source_file:
            while chunk := source_file.read(1024 * 1024):
                hasher.update(chunk)
        hasher.update(str(path.relative_to(source_path)).encode())
    return hasher.hexdigest()


def _reject_symlinks(source_path: Path) -> None:
    paths = [source_path]
    if source_path.is_dir():
        paths.extend(source_path.rglob("*"))
    linked = next((path for path in paths if path.is_symlink()), None)
    if linked is not None:
        raise ValueError(f"Symbolic links are not allowed in pool input: {linked}")


def validate_regular_tree(root: Path) -> None:
    """Reject links and special files without following them."""
    try:
        root_mode = root.lstat().st_mode
    except FileNotFoundError:
        raise FileNotFoundError(f"Pool path not found: {root}") from None
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise UnsafePoolError(f"Unsafe pool path: {root}")

    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            candidate = Path(current) / name
            mode = candidate.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise UnsafePoolError(
                    f"Symbolic links are not allowed in pools: {candidate.relative_to(root)}"
                )
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise UnsafePoolError(
                    f"Special files are not allowed in pools: {candidate.relative_to(root)}"
                )


class PoolManager:
    def __init__(self, pool_root: str):
        self.pool_root = Path(pool_root).expanduser().resolve()

    def create(
        self,
        source: str,
        pool_name: Optional[str] = None,
        reuse: bool = False,
    ) -> str:
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source}")
        _reject_symlinks(Path(source).expanduser().absolute())

        name = _resolve_name(self.pool_root, pool_name, source)

        if reuse:
            try:
                self.validate(name)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Pool {name!r} not found. "
                    f"Ohne --reuse-pool aufrufen, um ihn anzulegen."
                ) from None
        else:
            self._init_pool(name, source_path)

        return name

    def _init_pool(self, name: str, source_path: Path) -> None:
        self.pool_root.mkdir(parents=True, exist_ok=True)
        pool_dir = self.pool_root / name
        staging = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=self.pool_root))
        try:
            input_dir = staging / "input"
            input_dir.mkdir()
            (staging / "scripts").mkdir()
            (staging / "output").mkdir()
            (staging / "logs").mkdir()

            try:
                os.chmod(staging / "output", 0o777)
                os.chmod(staging / "logs", 0o777)
            except OSError:
                pass

            if source_path.is_dir():
                shutil.copytree(source_path, input_dir / source_path.name)
            else:
                shutil.copy2(source_path, input_dir / source_path.name)

            pool_meta = {
                "schema_version": 1,
                "pool_name": name,
                "sandbox_image": "llmflask-sandbox:1",
                "entrypoint": "run.sh",
                "source_path": str(source_path),
                "input_hash": _compute_hash(source_path),
                "requirements_hash": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_run": None,
            }
            (staging / "pool.json").write_text(
                json.dumps(pool_meta, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            staging.rename(pool_dir)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def exists(self, name: str) -> bool:
        _validate_pool_name(name)
        path = self.pool_root / name
        return not path.is_symlink() and path.is_dir()

    def pool_path(self, name: str) -> Path:
        _validate_pool_name(name)
        path = self.pool_root / name
        if path.is_symlink():
            raise UnsafePoolError(f"Pool path must not be a symbolic link: {name!r}")
        if not path.is_dir():
            raise FileNotFoundError(f"Pool not found: {name!r}")
        return path

    def validate(self, name: str) -> Path:
        path = self.pool_path(name)
        validate_regular_tree(path)
        return path

    def list_pools(self) -> list[dict]:
        pools: list[dict] = []
        if not self.pool_root.is_dir():
            return pools
        for entry in sorted(self.pool_root.iterdir()):
            if entry.is_symlink() or not entry.is_dir():
                continue
            try:
                validate_regular_tree(entry)
            except UnsafePoolError as exc:
                pools.append(
                    {
                        "name": entry.name,
                        "source_path": "",
                        "created_at": "",
                        "last_run": None,
                        "unsafe": str(exc),
                    }
                )
                continue
            meta_file = entry / "pool.json"
            if not meta_file.is_file():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                import sys
                print(f"Warning: corrupt pool.json in {entry.name}", file=sys.stderr)
                continue
            pools.append(
                {
                    "name": entry.name,
                    "source_path": meta.get("source_path", ""),
                    "created_at": meta.get("created_at", ""),
                    "last_run": meta.get("last_run"),
                }
            )
        return pools

    def load_meta(self, name: str) -> dict:
        path = self.validate(name)
        meta_file = path / "pool.json"
        if not meta_file.is_file():
            return {"pool_name": name}
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"pool_name": name}

    def save_meta(self, name: str, meta: dict) -> None:
        path = self.validate(name)
        atomic_write(
            path / "pool.json",
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        )

    def remove(self, name: str) -> None:
        pool_dir = self.pool_path(name)
        shutil.rmtree(pool_dir)

    def pack(self, name: str, output: Optional[str] = None, without_input: bool = False) -> str:
        pool_dir = self.validate(name)
        archive_name = output or f"{name}.tar.gz"
        archive_path = Path(archive_name).expanduser().resolve()
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        exclude = []
        if without_input:
            exclude.append("input")

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{archive_path.name}-", suffix=".tmp", dir=archive_path.parent
        )
        os.close(fd)
        temporary_path = Path(temporary_name)
        cmd = ["tar", "-czf", str(temporary_path)]
        for e in exclude:
            cmd.extend(["--exclude", e])
        cmd.extend(["-C", str(pool_dir.parent), name])

        try:
            subprocess.run(cmd, check=True)
            os.replace(temporary_path, archive_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return str(archive_path)
