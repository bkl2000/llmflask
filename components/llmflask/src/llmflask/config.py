# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os
import re
import shutil
from pathlib import Path


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def is_safe_name(name: str) -> bool:
    return bool(_SAFE_NAME_RE.fullmatch(name)) and name not in (".", "..")


def default_database_path() -> str:
    data_home = os.getenv("XDG_DATA_HOME")
    if data_home:
        base = Path(data_home).expanduser()
    else:
        base = Path.home() / ".local" / "share"
    return str((base / "llmflask" / "chat.db").resolve())


def default_data_path(*parts: str) -> str:
    data_home = os.getenv("XDG_DATA_HOME")
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return str((base / "llmflask" / Path(*parts)).resolve())


def migrate_legacy_database(destination: str):
    if os.getenv("LLMFLASK_DB"):
        return

    dest = Path(destination).expanduser()
    source = Path.cwd() / "chat.db"
    if not source.exists() or dest.exists() or source.resolve() == dest.resolve():
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{source}{suffix}")
        if sidecar.exists():
            shutil.copy2(sidecar, Path(f"{dest}{suffix}"))


def configured_database_path() -> str:
    configured = os.getenv("LLMFLASK_DB")
    if configured:
        return str(Path(configured).expanduser())
    return default_database_path()


def prepare_database_path(path: str) -> str:
    db_path = Path(path).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    migrate_legacy_database(str(db_path))
    return str(db_path)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8071")
HOST = os.getenv("LLMFLASK_HOST", "127.0.0.1")
PORT = int(os.getenv("LLMFLASK_PORT", "5000"))
TRUSTED_HOSTS = os.getenv("LLMFLASK_TRUSTED_HOSTS", "")
DATABASE = configured_database_path()
DEFAULT_USER = os.getenv("LLMFLASK_USER", "default")
NUM_CTX = int(os.getenv("LLMFLASK_NUM_CTX", "8192"))
MAX_CONTEXT_MESSAGES = int(os.getenv("LLMFLASK_MAX_CONTEXT_MSGS", "30"))

WORKBENCH_ENABLED = os.getenv("LLMFLASK_WORKBENCH_ENABLED", "0") == "1"
SANDBOX_RUNTIME = os.getenv("LLMFLASK_SANDBOX_RUNTIME", "docker")
SANDBOX_IMAGE = os.getenv("LLMFLASK_SANDBOX_IMAGE", "llmflask-sandbox:1")
POOL_ROOT = os.getenv("LLMFLASK_POOL_ROOT", str(Path.home() / ".local" / "share" / "llmflask" / "pools"))
POOL_ARCHIVE_ROOT = os.getenv("LLMFLASK_POOL_ARCHIVE_ROOT", default_data_path("archives"))
MAX_UPLOAD_BYTES = int(os.getenv("LLMFLASK_MAX_UPLOAD_BYTES", str(512 * 1024 * 1024)))
MAX_UPLOAD_FILE_BYTES = int(os.getenv("LLMFLASK_MAX_UPLOAD_FILE_BYTES", str(256 * 1024 * 1024)))
MAX_UPLOAD_FILES = int(os.getenv("LLMFLASK_MAX_UPLOAD_FILES", "1000"))
SANDBOX_TIMEOUT = int(os.getenv("LLMFLASK_SANDBOX_TIMEOUT", "60"))
SANDBOX_MEMORY = os.getenv("LLMFLASK_SANDBOX_MEMORY", "2g")
SANDBOX_CPUS = os.getenv("LLMFLASK_SANDBOX_CPUS", "2")
SANDBOX_PIDS_LIMIT = int(os.getenv("LLMFLASK_SANDBOX_PIDS_LIMIT", "128"))
SANDBOX_MAX_STDOUT = int(os.getenv("LLMFLASK_SANDBOX_MAX_STDOUT", "1000000"))
SANDBOX_MAX_STDERR = int(os.getenv("LLMFLASK_SANDBOX_MAX_STDERR", "1000000"))
SANDBOX_MAX_ARTIFACTS = int(os.getenv("LLMFLASK_SANDBOX_MAX_ARTIFACTS", "20"))
SANDBOX_MAX_ARTIFACT_BYTES = int(os.getenv("LLMFLASK_SANDBOX_MAX_ARTIFACT_BYTES", "100000000"))
SANDBOX_MAX_TOTAL_ARTIFACT_BYTES = int(os.getenv("LLMFLASK_SANDBOX_MAX_TOTAL_ARTIFACT_BYTES", "100000000"))
SANDBOX_REPAIR_ATTEMPTS = int(os.getenv("LLMFLASK_SANDBOX_REPAIR_ATTEMPTS", "1"))
RESULT_DIR = os.getenv("LLMFLASK_RESULT_DIR", str(Path.home() / "llmflask-results"))
