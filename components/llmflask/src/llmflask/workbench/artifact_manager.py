# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import tempfile
from pathlib import Path


def atomic_write(target: Path, content: str) -> None:
    target = Path(target).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".tmp-{target.name}-",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.rename(tmp_path, target)
        try:
            os.chmod(target, 0o644)
        except OSError:
            pass
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_copy(source: Path, target: Path) -> None:
    source = Path(source).expanduser().resolve()
    target = Path(target).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".tmp-{target.name}-",
    )
    try:
        os.close(tmp_fd)
        with open(source, "rb") as src:
            with open(tmp_path, "wb") as dst:
                dst.write(src.read())
        os.rename(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def backup_existing(target: Path) -> Path | None:
    target = Path(target).expanduser().resolve()
    if not target.exists():
        return None
    backup = Path(str(target) + ".backup")
    os.rename(target, backup)
    return Path(backup)


def restore_backup(backup: Path, target: Path) -> None:
    backup = Path(backup).expanduser().resolve()
    target = Path(target).expanduser().resolve()
    if backup.exists():
        os.rename(backup, target)


def discard_backup(backup: Path) -> None:
    backup = Path(backup).expanduser().resolve()
    try:
        os.unlink(backup)
    except OSError:
        pass
